"""Custom MaaFramework extensions are registered here when JSON is insufficient."""

from maa.agent.agent_server import AgentServer

from flowerbed.maa_backend import SoleilFlowerbedAutoAction


AgentServer.register_custom_action(
    "SoleilFlowerbedAuto",
    SoleilFlowerbedAutoAction(),
)
