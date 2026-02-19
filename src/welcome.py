"""
Kore — Welcome message shown after installation.
"""

BANNER = r"""
\033[38;5;105m
  ██╗  ██╗ ██████╗ ██████╗ ███████╗
  ██║ ██╔╝██╔═══██╗██╔══██╗██╔════╝
  █████╔╝ ██║   ██║██████╔╝█████╗
  ██╔═██╗ ██║   ██║██╔══██╗██╔══╝
  ██║  ██╗╚██████╔╝██║  ██║███████╗
  ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝
\033[0m"""

TAGLINE = "\033[38;5;147m  memory layer for AI agents — remembers what matters, forgets what doesn't\033[0m"

QUICK_START = """
\033[38;5;244m  ─────────────────────────────────────────────────\033[0m
\033[1m  Quick Start\033[0m

  \033[38;5;147m$\033[0m kore                    \033[38;5;244m# start server on :8765\033[0m
  \033[38;5;147m$\033[0m curl localhost:8765/health

  \033[38;5;147m$\033[0m curl -X POST localhost:8765/save \\
      -d '{\"content\": \"your first memory\", \"category\": \"general\"}'

\033[38;5;244m  ─────────────────────────────────────────────────\033[0m
  \033[38;5;75mhttps://github.com/auriti-web-design/kore-memory\033[0m
\033[38;5;244m  ─────────────────────────────────────────────────\033[0m
"""


def print_welcome() -> None:
    print(BANNER)
    print(TAGLINE)
    print(QUICK_START)


if __name__ == "__main__":
    print_welcome()
