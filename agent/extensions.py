"""Register custom recognition and actions used by the AgentServer entry point."""

from maa.agent.agent_server import AgentServer

if __package__:
    from .recovery import register_recovery
    from .furniture_timer import register_furniture_timer
else:
    from recovery import register_recovery
    from furniture_timer import register_furniture_timer


register_recovery(AgentServer)
register_furniture_timer(AgentServer)
