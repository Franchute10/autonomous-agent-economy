from aeos.economics import (
    EconomicTransaction,
    EconomicTransactionType,
    EmptyTransaction,
    LedgerPosting,
    MissingResourceAccountDefinition,
    MissingResourceDefinition,
    PostingResourceMismatch,
    PostingUnitMismatch,
    Resource,
    ResourceAccount,
    ResourceAccountType,
    TransactionOrganizationMismatch,
    UnbalancedEconomicTransaction,
    ZeroPosting,
)


def test_economics_facade_exports_public_contracts() -> None:
    assert Resource.__name__ == "Resource"
    assert ResourceAccount.__name__ == "ResourceAccount"
    assert ResourceAccountType.__name__ == "ResourceAccountType"
    assert EconomicTransaction.__name__ == "EconomicTransaction"
    assert EconomicTransactionType.__name__ == "EconomicTransactionType"
    assert LedgerPosting.__name__ == "LedgerPosting"
    assert {
        error.__name__
        for error in (
            ZeroPosting,
            EmptyTransaction,
            UnbalancedEconomicTransaction,
            PostingResourceMismatch,
            PostingUnitMismatch,
            TransactionOrganizationMismatch,
            MissingResourceDefinition,
            MissingResourceAccountDefinition,
        )
    } == {
        "ZeroPosting",
        "EmptyTransaction",
        "UnbalancedEconomicTransaction",
        "PostingResourceMismatch",
        "PostingUnitMismatch",
        "TransactionOrganizationMismatch",
        "MissingResourceDefinition",
        "MissingResourceAccountDefinition",
    }
