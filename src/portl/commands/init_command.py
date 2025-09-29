from pathlib import Path
from typing import Optional

from ..ui.console import ConsoleUI


class InitCommandHandler:
    def __init__(self):
        self.ui = ConsoleUI()
    
    def handle(
        self,
        output: Optional[Path] = None,
        interactive: bool = True
    ):
        self.ui.print_welcome_banner()
        
        if interactive:
            self.ui.print_coming_soon("Interactive wizard mode")
            self.ui.print_init_features()
        else:
            self.ui.print_not_implemented("Non-interactive mode")
        
        if output:
            self.ui.print_info(f"\n[dim]Output will be saved to: {output}[/dim]")
        
        self.ui.print_info(
            "\nFor now, check out the documentation at: "
            "[link]https://github.com/hebaghazali/portl[/link]"
        )
