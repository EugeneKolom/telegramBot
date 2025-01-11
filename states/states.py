from aiogram.fsm.state import State, StatesGroup

class BotStates(StatesGroup):
    waiting_for_keywords = State()
    waiting_for_group_name = State()
    waiting_for_settings = State()
    waiting_for_invite_group_id = State()
    waiting_for_manual_group = State()
    waiting_for_group_to_parse = State()
    selecting_groups = State() 
    deleting_groups = State()