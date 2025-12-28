"""
Conditional step executor for if/then/else branching.

Evaluates a condition and executes appropriate branch steps.
"""

import logging
from typing import List, Dict, Any

from ..executor import register_executor
from ..context import ExecutionContext, StepResult, StepStatus
from ..templating import get_template_engine
from ...schema import BaseStep, Step as DataclassStep

logger = logging.getLogger(__name__)


@register_executor("conditional")
class ConditionalExecutor:
    """Executor for conditional step type with then/else branching."""
    
    def execute(self, step: BaseStep, context: ExecutionContext) -> StepResult:
        """
        Execute conditional branching logic.
        
        Evaluates the 'when' condition and executes either 'then' or 'else' branch.
        
        Args:
            step: Conditional step configuration
            context: Execution context
            
        Returns:
            StepResult aggregating results from executed branch
        """
        # Get engine reference from context (injected by JobEngine)
        engine = context.current_vars.get('_engine')
        if not engine:
            raise RuntimeError(
                "Conditional executor requires engine reference in context. "
                "Engine should inject '_engine' before dispatching conditional steps."
            )
        
        # Extract configuration
        if hasattr(step, 'config') and isinstance(step.config, dict):
            # Dataclass Step
            config = step.config
            condition = step.when or config.get('when')
            then_steps = config.get('then', [])
            else_steps = config.get('else', [])
        else:
            # Pydantic Step
            condition = step.when
            then_steps = getattr(step, 'then', [])
            else_steps = getattr(step, 'else_', []) or getattr(step, 'else', [])
        
        if not condition:
            raise ValueError(f"Conditional step '{step.id}' requires 'when' condition")
        
        # Evaluate condition
        template_engine = get_template_engine()
        template_context = context.to_template_dict()
        
        try:
            # Evaluate condition expression
            condition_result = template_engine.evaluate_condition(condition, template_context)
            logger.info(
                f"Conditional '{step.id}' evaluated to {condition_result}",
                extra={'step_id': step.id, 'condition': condition}
            )
        except Exception as e:
            logger.error(f"Failed to evaluate condition '{condition}': {e}")
            raise ValueError(f"Condition evaluation failed in step '{step.id}': {e}")
        
        # Determine which branch to execute
        if condition_result:
            branch_steps = then_steps
            branch_name = 'then'
        else:
            branch_steps = else_steps
            branch_name = 'else'
        
        # If no steps in selected branch, return success
        if not branch_steps:
            logger.info(
                f"Conditional '{step.id}' selected '{branch_name}' branch with no steps",
                extra={'step_id': step.id}
            )
            return StepResult(
                step_id=step.id,
                status=StepStatus.OK,
                output={
                    'branch_taken': branch_name,
                    'condition': condition,
                    'evaluated_to': condition_result,
                    'steps_executed': 0,
                },
                metrics={
                    'branch': branch_name,
                    'steps_count': 0,
                },
            )
        
        logger.info(
            f"Executing '{branch_name}' branch with {len(branch_steps)} step(s)",
            extra={'step_id': step.id}
        )
        
        # Execute branch steps
        branch_results = []
        updated_context = context
        
        for branch_step_data in branch_steps:
            # Parse step data into Step object
            branch_step = self._parse_step_data(branch_step_data)
            
            try:
                # Execute the branch step through the engine
                # This maintains transaction scope and compensation tracking
                updated_context = engine._execute_step(branch_step, updated_context)
                
                # Collect result
                step_result = updated_context.get_step_result(branch_step.id)
                if step_result:
                    branch_results.append({
                        'step_id': branch_step.id,
                        'status': step_result.status.value,
                        'output': step_result.output,
                    })
                
                # Check if step failed
                if step_result and step_result.status == StepStatus.ERROR:
                    logger.error(
                        f"Branch step '{branch_step.id}' failed in conditional '{step.id}'"
                    )
                    # Propagate error
                    return StepResult(
                        step_id=step.id,
                        status=StepStatus.ERROR,
                        output=None,
                        metrics={'branch': branch_name, 'failed_step': branch_step.id},
                        error=step_result.error,
                    )
            
            except Exception as e:
                logger.error(
                    f"Error executing branch step '{branch_step.id}' in conditional '{step.id}': {e}"
                )
                return StepResult(
                    step_id=step.id,
                    status=StepStatus.ERROR,
                    output=None,
                    metrics={'branch': branch_name, 'failed_step': branch_step.id},
                    error=e,
                )
        
        # All branch steps succeeded
        logger.info(
            f"Conditional '{step.id}' completed successfully ({branch_name} branch, {len(branch_results)} steps)",
            extra={'step_id': step.id}
        )
        
        return StepResult(
            step_id=step.id,
            status=StepStatus.OK,
            output={
                'branch_taken': branch_name,
                'condition': condition,
                'evaluated_to': condition_result,
                'steps_executed': len(branch_results),
                'results': branch_results,
            },
            metrics={
                'branch': branch_name,
                'steps_count': len(branch_results),
            },
        )
    
    def _parse_step_data(self, step_data: Dict[str, Any]) -> BaseStep:
        """
        Parse step data dictionary into Step object.
        
        Args:
            step_data: Raw step configuration dict
            
        Returns:
            Step object
        """
        # Extract base fields
        step_id = step_data.get('id')
        step_type = step_data.get('type')
        connection = step_data.get('connection')
        save_as = step_data.get('save_as')
        when = step_data.get('when')
        
        if not step_id or not step_type:
            raise ValueError("Branch step must have 'id' and 'type' fields")
        
        # Extract step-specific config (everything except base fields)
        base_fields = {'id', 'type', 'connection', 'save_as', 'when', 'batch', 'retry',
                      'on_error', 'compensate_with'}
        config = {k: v for k, v in step_data.items() if k not in base_fields}
        
        # Create Step object
        return DataclassStep(
            id=step_id,
            type=step_type,
            connection=connection,
            save_as=save_as,
            when=when,
            config=config,
        )

