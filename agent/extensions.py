"""Register custom recognition and actions used by the AgentServer entry point."""

from maa.agent.agent_server import AgentServer

if __package__:
    from .recovery import register_recovery
    from .furniture_timer import register_furniture_timer
    from .ad_close import register_ad_close
    from .delivery import register_delivery
    from .login import register_login
else:
    from recovery import register_recovery
    from furniture_timer import register_furniture_timer
    from ad_close import register_ad_close
    from delivery import register_delivery
    from login import register_login


register_recovery(AgentServer)
register_furniture_timer(AgentServer)
register_ad_close(AgentServer)
register_delivery(AgentServer)
register_login(AgentServer)
