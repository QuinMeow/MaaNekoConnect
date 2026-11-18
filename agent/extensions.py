"""Register custom recognition and actions used by the AgentServer entry point."""

from maa.agent.agent_server import AgentServer

if __package__:
    from .recovery import register_recovery
    from .furniture_timer import register_furniture_timer
    from .ad_close import register_ad_close
    from .delivery import register_delivery
    from .login import register_login
    from .soleil import register_soleil
    from .contest import register_contest
    from .gift import register_gift
    from .exchange import register_exchange
else:
    from recovery import register_recovery
    from furniture_timer import register_furniture_timer
    from ad_close import register_ad_close
    from delivery import register_delivery
    from login import register_login
    from soleil import register_soleil
    from contest import register_contest
    from gift import register_gift
    from exchange import register_exchange


register_recovery(AgentServer)
register_furniture_timer(AgentServer)
register_ad_close(AgentServer)
register_delivery(AgentServer)
register_login(AgentServer)
register_soleil(AgentServer)
register_contest(AgentServer)
register_gift(AgentServer)
register_exchange(AgentServer)
