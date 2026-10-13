"""Explicit live AWS check. Success is printed only after Converse returns valid intent."""
from .providers import BedrockProvider
from .store import demo_now

if __name__ == "__main__":
    intent = BedrockProvider().parse("Charge my EV before 7 AM using the cheapest available electricity.", demo_now())
    print("LIVE BEDROCK CONVERSE SUCCEEDED:", intent.model_dump_json())
