"""Feature assembly for analysis services."""


def combine_features(context: dict, history: dict) -> dict:
    return {"context": context, "history": history}
