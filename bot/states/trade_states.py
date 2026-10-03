from aiogram.fsm.state import State, StatesGroup


class TradeCreate(StatesGroup):
    coin = State()
    direction = State()
    risk = State()
    risk_custom = State()
    entry = State()
    stop_loss = State()
    setup_tag = State()
    screenshot = State()


class TradeClose(StatesGroup):
    rr_custom = State()
    emotion_tag = State()
    screenshot = State()


class LeverageCalc(StatesGroup):
    distance = State()
    risk_amount = State()


class SettingsFlow(StatesGroup):
    margin = State()
    daily_risk_limit = State()


class CustomPeriod(StatesGroup):
    start_date = State()
    end_date = State()


class RestoreConfirm(StatesGroup):
    confirm = State()


class AlertCreate(StatesGroup):
    coin = State()
    price = State()
