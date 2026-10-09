from app.repositories.social_account_repository import (
    save_social_account,
    get_social_accounts,
    get_social_account_by_id,
)

USER_ID = 1


def main():
    print("\n=== TEST 1: Save Facebook Account 1 ===")

    account_1 = save_social_account(
        user_id=USER_ID,
        platform="facebook",
        access_token="test_token_facebook_1",
        page_id="facebook_page_101",
        account_name="Facebook Page 1",
        account_email="page1@example.com",
    )

    print("Account 1:", account_1)

    print("\n=== TEST 2: Save Facebook Account 2 ===")

    account_2 = save_social_account(
        user_id=USER_ID,
        platform="facebook",
        access_token="test_token_facebook_2",
        page_id="facebook_page_102",
        account_name="Facebook Page 2",
        account_email="page2@example.com",
    )

    print("Account 2:", account_2)

    print("\n=== TEST 3: Get All Facebook Accounts ===")

    accounts = get_social_accounts(
        user_id=USER_ID,
        platform="facebook",
    )

    for account in accounts:
        print(account)

    print(f"\nTotal Facebook accounts: {len(accounts)}")

    print("\n=== TEST 4: Get Account By ID ===")

    account_id = account_1["id"]

    account = get_social_account_by_id(
        account_id=account_id,
        user_id=USER_ID,
    )

    print("Account found:")
    print(account)

print("\n=== TEST 5: Update Existing Facebook Account ===")

updated_account = save_social_account(
    user_id=USER_ID,
    platform="facebook",
    access_token="updated_token_for_page_101",
    page_id="facebook_page_101",
    account_name="Facebook Page 1 Updated",
    account_email="updated_page1@example.com",
)

print("Updated account:", updated_account)

accounts = get_social_accounts(
    user_id=USER_ID,
    platform="facebook",
)

print(f"\nTotal Facebook accounts after update: {len(accounts)}")

for account in accounts:
    print(
        account["id"],
        account["page_id"],
        account["account_name"],
    )

if __name__ == "__main__":
    main()