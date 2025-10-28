"""
Execution context for job orchestration.

Provides immutable snapshot-based context passing between steps with
a small mutable globals section for run-wide constants.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid


class StepStatus(str, Enum):
    """Status of step execution."""
    OK = "ok"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class StepResult:
    """
    Immutable result snapshot from a step execution.
    
    Each step produces exactly one StepResult that gets stored in the
    ExecutionContext by step ID.
    """
    step_id: str
    status: StepStatus
    output: Any  # Type-specific: rows (List[Dict]), record (Dict), response, etc.
    metrics: Dict[str, Any] = field(default_factory=dict)
    error: Optional[Exception] = None
    
    # Transaction markers (for DB steps)
    touched_transaction: bool = False
    
    def __post_init__(self):
        """Validate result consistency."""
        if self.status == StepStatus.ERROR and self.error is None:
            raise ValueError("ERROR status requires an error")
        if self.status == StepStatus.OK and self.error is not None:
            raise ValueError("OK status cannot have an error")


class ExecutionContext:
    """
    Execution context for a job run.
    
    Architecture:
    - globals: mutable dict for run-wide constants (run_id, env vars, secrets)
    - steps: immutable dict of step_id -> StepResult (append-only)
    - current_vars: ephemeral per-step locals (for loop iteration, with_ctx)
    
    Design rationale:
    - Immutable step results enable debugging (inspect context at any point)
    - Thread-safe for future parallelization
    - Provides audit trail (we don't rewrite history on rollback)
    """
    
    def __init__(
        self,
        run_id: Optional[str] = None,
        globals_dict: Optional[Dict[str, Any]] = None,
        step_results: Optional[Dict[str, StepResult]] = None,
        current_vars: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize execution context.
        
        Args:
            run_id: Unique identifier for this job run
            globals_dict: Run-wide constants (env, secrets, run metadata)
            step_results: Previously executed step results (for immutable snapshots)
            current_vars: Ephemeral variables for current step execution
        """
        self.run_id = run_id or str(uuid.uuid4())
        self.globals = globals_dict or {}
        
        # Immutable snapshots (append-only)
        self._step_results: Dict[str, StepResult] = step_results or {}
        
        # Ephemeral per-step state
        self.current_vars = current_vars or {}
        
        # Initialize globals if empty
        if not self.globals:
            self.globals = {
                'run_id': self.run_id,
                'started_at': datetime.utcnow().isoformat(),
            }
    
    @classmethod
    def new(
        cls,
        run_id: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        secrets: Optional[Dict[str, str]] = None
    ) -> 'ExecutionContext':
        """
        Create a new execution context for a job run.
        
        Args:
            run_id: Optional run identifier (generated if not provided)
            env: Environment variables to expose in templates
            secrets: Secret values (never logged)
            
        Returns:
            New ExecutionContext instance
        """
        run_id = run_id or str(uuid.uuid4())
        globals_dict = {
            'run_id': run_id,
            'started_at': datetime.utcnow().isoformat(),
            'env': env or {},
            'secrets': secrets or {},
        }
        return cls(run_id=run_id, globals_dict=globals_dict)
    
    def with_step_result(self, step_id: str, result: StepResult) -> 'ExecutionContext':
        """
        Return new context with additional step result.
        
        This creates a new context with the result appended to the immutable
        step results dict. The original context is unchanged.
        
        Args:
            step_id: Step identifier
            result: Step execution result
            
        Returns:
            New ExecutionContext with result added
        """
        if step_id in self._step_results:
            raise ValueError(f"Step '{step_id}' already has a result in context")
        
        new_results = {**self._step_results, step_id: result}
        
        return ExecutionContext(
            run_id=self.run_id,
            globals_dict=self.globals,
            step_results=new_results,
            current_vars={}  # Clear ephemeral vars for next step
        )
    
    def with_vars(self, **vars_dict: Any) -> 'ExecutionContext':
        """
        Return new context with updated ephemeral variables.
        
        Used for loop iteration (item, index) or step-local with_ctx.
        
        Args:
            **vars_dict: Variables to set
            
        Returns:
            New ExecutionContext with updated current_vars
        """
        new_vars = {**self.current_vars, **vars_dict}
        
        return ExecutionContext(
            run_id=self.run_id,
            globals_dict=self.globals,
            step_results=self._step_results,
            current_vars=new_vars
        )
    
    def get_step_result(self, step_id: str) -> Optional[StepResult]:
        """
        Get result for a specific step.
        
        Args:
            step_id: Step identifier
            
        Returns:
            StepResult if step has executed, None otherwise
        """
        return self._step_results.get(step_id)
    
    def has_step_result(self, step_id: str) -> bool:
        """Check if a step has executed and produced a result."""
        return step_id in self._step_results
    
    @property
    def steps(self) -> Dict[str, Any]:
        """
        Get step results formatted for template access.
        
        Returns dict where each step's output is accessible as:
        - steps.step_id.rows (for plural results)
        - steps.step_id.record (for singular results)
        - steps.step_id (for direct access to output)
        
        Returns:
            Dict suitable for Jinja2 template context
        """
        formatted = {}
        
        for step_id, result in self._step_results.items():
            if result.status == StepStatus.OK:
                # Create accessor object
                output = result.output
                
                # Support both singular and plural access patterns
                if isinstance(output, list):
                    formatted[step_id] = {
                        'rows': output,
                        'output': output,
                        'count': len(output),
                    }
                elif isinstance(output, dict):
                    formatted[step_id] = {
                        'record': output,
                        'output': output,
                        **output,  # Allow direct field access
                    }
                else:
                    formatted[step_id] = {
                        'output': output,
                    }
        
        return formatted
    
    def to_template_dict(self) -> Dict[str, Any]:
        """
        Get complete context for Jinja2 template rendering.
        
        Returns:
            Dict with globals, steps, and current_vars merged
        """
        return {
            **self.globals,
            'steps': self.steps,
            **self.current_vars,
        }
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get summary metrics for all executed steps.
        
        Returns:
            Summary statistics
        """
        total_steps = len(self._step_results)
        ok_steps = sum(1 for r in self._step_results.values() if r.status == StepStatus.OK)
        error_steps = sum(1 for r in self._step_results.values() if r.status == StepStatus.ERROR)
        skipped_steps = sum(1 for r in self._step_results.values() if r.status == StepStatus.SKIPPED)
        
        return {
            'total_steps': total_steps,
            'ok_steps': ok_steps,
            'error_steps': error_steps,
            'skipped_steps': skipped_steps,
            'run_id': self.run_id,
        }

