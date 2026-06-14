import sys

from maa.agent.agent_server import AgentServer
from maa.toolkit import Toolkit

import extensions  # noqa: F401


def main():
    Toolkit.init_option("./")

    if len(sys.argv) < 2:
        raise SystemExit("Usage: python agent/main.py <socket_id>")

    AgentServer.start_up(sys.argv[-1])
    AgentServer.join()
    AgentServer.shut_down()


if __name__ == "__main__":
    main()
