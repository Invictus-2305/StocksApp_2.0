from brokers.angel_one import AngelOneBroker

class BrokerFactory:
    """
    Factory to return broker specialized classes based on string preference.
    """
    _brokers = {
        "angelone": AngelOneBroker,
        # "zerodha": ZerodhaBroker, (future)
    }

    @classmethod
    def get_broker(cls, broker_name: str):
        broker_class = cls._brokers.get(broker_name.lower())
        if broker_class:
            return broker_class()
        return None
