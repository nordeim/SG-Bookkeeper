# File: tests/unit/services/test_account_type_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import List, Optional
from decimal import Decimal # Though not directly used by AccountType, good for context

from app.services.accounting_services import AccountTypeService
from app.models.accounting.account_type import AccountType as AccountTypeModel
from app.core.database_manager import DatabaseManager

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_session() -> AsyncMock:
    """Fixture to create a mock AsyncSession."""
    session = AsyncMock()
    session.get = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.delete = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session

@pytest.fixture
def mock_db_manager(mock_session: AsyncMock) -> MagicMock:
    """Fixture to create a mock DatabaseManager that returns the mock_session."""
    db_manager = MagicMock(spec=DatabaseManager)
    # Make the async context manager work
    db_manager.session.return_value.__aenter__.return_value = mock_session
    db_manager.session.return_value.__aexit__.return_value = None
    return db_manager

@pytest.fixture
def account_type_service(mock_db_manager: MagicMock) -> AccountTypeService:
    """Fixture to create an AccountTypeService instance with a mocked db_manager."""
    # AccountTypeService constructor takes db_manager and optional app_core
    # For unit tests, we typically don't need a full app_core if service only uses db_manager
    return AccountTypeService(db_manager=mock_db_manager, app_core=None)

# --- Test Cases ---

async def test_get_account_type_by_id_found(account_type_service: AccountTypeService, mock_session: AsyncMock):
    """Test get_by_id when AccountType is found."""
    expected_at = AccountTypeModel(id=1, name="Current Asset", category="Asset", is_debit_balance=True, report_type="BS", display_order=10)
    mock_session.get.return_value = expected_at

    result = await account_type_service.get_by_id(1)
    
    assert result == expected_at
    mock_session.get.assert_awaited_once_with(AccountTypeModel, 1)

async def test_get_account_type_by_id_not_found(account_type_service: AccountTypeService, mock_session: AsyncMock):
    """Test get_by_id when AccountType is not found."""
    mock_session.get.return_value = None

    result = await account_type_service.get_by_id(99)
    
    assert result is None
    mock_session.get.assert_awaited_once_with(AccountTypeModel, 99)

async def test_get_all_account_types(account_type_service: AccountTypeService, mock_session: AsyncMock):
    """Test get_all returns a list of AccountTypes."""
    at1 = AccountTypeModel(id=1, name="CA", category="Asset", is_debit_balance=True, report_type="BS", display_order=10)
    at2 = AccountTypeModel(id=2, name="CL", category="Liability", is_debit_balance=False, report_type="BS", display_order=20)
    mock_execute_result = AsyncMock()
    mock_execute_result.scalars.return_value.all.return_value = [at1, at2]
    mock_session.execute.return_value = mock_execute_result

    result = await account_type_service.get_all()

    assert len(result) == 2
    assert result[0].name == "CA"
    assert result[1].name == "CL"
    mock_session.execute.assert_awaited_once()
    # We can also assert the statement passed to execute if needed, but it's more complex

async def test_add_account_type(account_type_service: AccountTypeService, mock_session: AsyncMock):
    """Test adding a new AccountType."""
    new_at_data = AccountTypeModel(name="New Type", category="Equity", is_debit_balance=False, report_type="BS", display_order=30)
    
    # Configure refresh to work on the passed object
    async def mock_refresh(obj, attribute_names=None):
        pass # In a real scenario, this might populate obj.id if it's autogenerated
    mock_session.refresh.side_effect = mock_refresh

    result = await account_type_service.add(new_at_data)

    mock_session.add.assert_called_once_with(new_at_data)
    mock_session.flush.assert_awaited_once()
    mock_session.refresh.assert_awaited_once_with(new_at_data)
    assert result == new_at_data

async def test_update_account_type(account_type_service: AccountTypeService, mock_session: AsyncMock):
    """Test updating an existing AccountType."""
    existing_at = AccountTypeModel(id=1, name="Old Name", category="Asset", is_debit_balance=True, report_type="BS", display_order=5)
    existing_at.name = "Updated Name" # Simulate a change
    
    async def mock_refresh_update(obj, attribute_names=None):
        obj.updated_at = MagicMock() # Simulate timestamp update
    mock_session.refresh.side_effect = mock_refresh_update

    result = await account_type_service.update(existing_at)

    mock_session.add.assert_called_once_with(existing_at) # SQLAlchemy uses add for updates too if object is managed
    mock_session.flush.assert_awaited_once()
    mock_session.refresh.assert_awaited_once_with(existing_at)
    assert result.name == "Updated Name"

async def test_delete_account_type_found(account_type_service: AccountTypeService, mock_session: AsyncMock):
    """Test deleting an existing AccountType."""
    at_to_delete = AccountTypeModel(id=1, name="To Delete", category="Expense", is_debit_balance=True, report_type="PL", display_order=100)
    mock_session.get.return_value = at_to_delete

    result = await account_type_service.delete(1)

    assert result is True
    mock_session.get.assert_awaited_once_with(AccountTypeModel, 1)
    mock_session.delete.assert_awaited_once_with(at_to_delete)

async def test_delete_account_type_not_found(account_type_service: AccountTypeService, mock_session: AsyncMock):
    """Test deleting a non-existent AccountType."""
    mock_session.get.return_value = None

    result = await account_type_service.delete(99)

    assert result is False
    mock_session.get.assert_awaited_once_with(AccountTypeModel, 99)
    mock_session.delete.assert_not_called()

async def test_get_account_type_by_name_found(account_type_service: AccountTypeService, mock_session: AsyncMock):
    """Test get_by_name when AccountType is found."""
    expected_at = AccountTypeModel(id=1, name="Specific Asset", category="Asset", is_debit_balance=True, report_type="BS", display_order=10)
    mock_execute_result = AsyncMock()
    mock_execute_result.scalars.return_value.first.return_value = expected_at
    mock_session.execute.return_value = mock_execute_result
    
    result = await account_type_service.get_by_name("Specific Asset")
    
    assert result == expected_at
    mock_session.execute.assert_awaited_once() # Could add statement assertion

async def test_get_account_types_by_category(account_type_service: AccountTypeService, mock_session: AsyncMock):
    """Test get_by_category returns a list of matching AccountTypes."""
    at1 = AccountTypeModel(id=1, name="Cash", category="Asset", is_debit_balance=True, report_type="BS", display_order=10)
    at2 = AccountTypeModel(id=2, name="Bank", category="Asset", is_debit_balance=True, report_type="BS", display_order=11)
    mock_execute_result = AsyncMock()
    mock_execute_result.scalars.return_value.all.return_value = [at1, at2]
    mock_session.execute.return_value = mock_execute_result

    result = await account_type_service.get_by_category("Asset")

    assert len(result) == 2
    assert result[0].name == "Cash"
    assert result[1].category == "Asset"
    mock_session.execute.assert_awaited_once()
