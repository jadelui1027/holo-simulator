"""
hOCG Game Tools Package
=======================
Modular game engine for the hololive Official Card Game.

Modules:
  - card_types     : ActionType, ConditionType, CostType enums
  - card_data      : SUPPORT_CARD_DB registry + all card definitions
  - action_executor: SupportCardExecutor class
  - pick_resolver  : Support card pick resolution logic (mixin)
  - game_actions   : Game action handlers (mixin)
  - game_phases    : Setup/mulligan/dice phase handlers (mixin)
  - game_state     : State serialization & queries (mixin)
  - game_engine    : Match orchestrator (composes all mixins)
  - playmat_manager: PlaymatManager, Zone, Card, ZoneInfo
  - server         : FastAPI WebSocket server
"""
