def user_profile_key(user_id: int) -> str:
    return f"spendwise:v1:user:{user_id}:profile"


def transaction_list_key(user_id: int, filters_hash: str, page: int) -> str:
    return f"spendwise:v1:txn:list:user:{user_id}:page:{page}:hash:{filters_hash}"


def report_monthly_key(user_id: int, year: int, month: int) -> str:
    return f"spendwise:v1:report:monthly:user:{user_id}:{year}:{month}"
