from pydantic import ValidationError
from app.schemas.verification import VerificationSettingsInput


def test_cleanup_exclusions_preserve_snowflakes_and_remove_duplicates():
    value = VerificationSettingsInput(cleanup_excluded_message_ids=" 1520855507760316436,\n1520855507760316436, 1520855507760316437 ")
    assert value.cleanup_excluded_message_ids == "1520855507760316436,1520855507760316437"


def test_cleanup_exclusions_reject_invalid_ids():
    for value in ("-1", "0", "123abc", "9999999999999999999999"):
        try:
            VerificationSettingsInput(cleanup_excluded_message_ids=value)
        except ValidationError:
            continue
        raise AssertionError(f"Invalid ID accepted: {value}")
