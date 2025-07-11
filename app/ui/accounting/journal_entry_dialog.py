# File: app/ui/accounting/journal_entry_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDateEdit, QComboBox,
    QPushButton, QDialogButtonBox, QMessageBox, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QHeaderView, QDoubleSpinBox, QApplication, QStyledItemDelegate,
    QAbstractSpinBox # For QDoubleSpinBox.NoButtons
)
from PySide6.QtCore import Qt, QDate, Slot, Signal, QTimer, QMetaObject, Q_ARG
from PySide6.QtGui import QIcon, QKeySequence, QColor, QPalette # QKeySequence not used here, but kept from original for consistency
from typing import Optional, List, Dict, Any, TYPE_CHECKING, cast

from decimal import Decimal, InvalidOperation
import json
from datetime import date as python_date

from app.utils.pydantic_models import JournalEntryData, JournalEntryLineData
from app.models.accounting.account import Account
from app.models.accounting.tax_code import TaxCode
# from app.models.accounting.currency import Currency # Not directly used for line combos
from app.models.accounting.journal_entry import JournalEntry 
from app.common.enums import JournalTypeEnum 
from app.main import schedule_task_from_qt
from app.utils.json_helpers import json_converter, json_date_hook 
from app.utils.result import Result 

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore
    from PySide6.QtGui import QPaintDevice # For QWidget type hint

class JournalEntryDialog(QDialog):
    journal_entry_saved = Signal(int) # Emits the ID of the saved/updated JE

    def __init__(self, app_core: "ApplicationCore", current_user_id: int, 
                 journal_entry_id: Optional[int] = None, 
                 view_only: bool = False, 
                 parent: Optional["QWidget"] = None): # QWidget type hint
        super().__init__(parent)
        self.app_core = app_core
        self.current_user_id = current_user_id
        self.journal_entry_id = journal_entry_id
        self.view_only_mode = view_only 
        self.loaded_journal_entry_orm: Optional[JournalEntry] = None 
        self.existing_journal_entry_data_dict: Optional[Dict[str, Any]] = None

        self._accounts_cache: List[Account] = []
        self._tax_codes_cache: List[TaxCode] = []
        
        self.setWindowTitle(self._get_window_title())
        self.setMinimumSize(900, 700)
        self.setModal(True)

        self._init_ui()
        self._connect_signals()

        QTimer.singleShot(0, lambda: schedule_task_from_qt(self._load_initial_combo_data()))
        if self.journal_entry_id:
            QTimer.singleShot(50, lambda: schedule_task_from_qt(self._load_existing_journal_entry()))
        elif not self.view_only_mode: 
            self._add_new_line() 
            self._add_new_line() 

    def _get_window_title(self) -> str:
        if self.view_only_mode: return "View Journal Entry"
        if self.journal_entry_id: return "Edit Journal Entry"
        return "New Journal Entry"

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        self.header_form = QFormLayout() # Made it an instance variable for disabling fields
        self.header_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.entry_date_edit = QDateEdit(QDate.currentDate())
        self.entry_date_edit.setCalendarPopup(True)
        self.entry_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.header_form.addRow("Entry Date*:", self.entry_date_edit)

        self.journal_type_combo = QComboBox()
        for jt_enum_member in JournalTypeEnum: self.journal_type_combo.addItem(jt_enum_member.value, jt_enum_member.value)
        self.journal_type_combo.setCurrentText(JournalTypeEnum.GENERAL.value)
        self.header_form.addRow("Journal Type:", self.journal_type_combo)
        
        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("Overall description for the journal entry")
        self.header_form.addRow("Description:", self.description_edit)

        self.reference_edit = QLineEdit()
        self.reference_edit.setPlaceholderText("e.g., Invoice #, Check #, Source Document ID")
        self.header_form.addRow("Reference:", self.reference_edit)
        
        main_layout.addLayout(self.header_form)

        self.lines_table = QTableWidget()
        self.lines_table.setColumnCount(7) 
        self.lines_table.setHorizontalHeaderLabels([
            "Account*", "Description", "Debit*", "Credit*", 
            "Tax Code", "Tax Amt", "" 
        ])
        header = self.lines_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch) 
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) 
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) 
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents) 
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents) 
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed) 
        self.lines_table.setColumnWidth(2, 130); self.lines_table.setColumnWidth(3, 130)
        self.lines_table.setColumnWidth(4, 160); self.lines_table.setColumnWidth(5, 110)
        self.lines_table.setColumnWidth(6, 30) 
        self.lines_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        main_layout.addWidget(self.lines_table)

        lines_button_layout = QHBoxLayout()
        icon_path_prefix = "resources/icons/" 
        try: import app.resources_rc; icon_path_prefix = ":/icons/"
        except ImportError: pass
        
        self.add_line_button = QPushButton(QIcon(icon_path_prefix + "add.svg"), "Add Line")
        self.remove_line_button = QPushButton(QIcon(icon_path_prefix + "remove.svg"), "Remove Selected Line")
        lines_button_layout.addWidget(self.add_line_button)
        lines_button_layout.addWidget(self.remove_line_button)
        lines_button_layout.addStretch()
        main_layout.addLayout(lines_button_layout)

        totals_layout = QHBoxLayout()
        totals_layout.addStretch()
        self.debits_label = QLabel("Debits: 0.00")
        self.credits_label = QLabel("Credits: 0.00")
        self.balance_label = QLabel("Balance: OK")
        self.balance_label.setStyleSheet("font-weight: bold;")
        totals_layout.addWidget(self.debits_label); totals_layout.addWidget(QLabel("  |  "));
        totals_layout.addWidget(self.credits_label); totals_layout.addWidget(QLabel("  |  "));
        totals_layout.addWidget(self.balance_label)
        main_layout.addLayout(totals_layout)

        self.button_box = QDialogButtonBox()
        self.save_draft_button = self.button_box.addButton("Save Draft", QDialogButtonBox.ButtonRole.ActionRole)
        self.save_post_button = self.button_box.addButton("Save & Post", QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.addButton(QDialogButtonBox.StandardButton.Close if self.view_only_mode else QDialogButtonBox.StandardButton.Cancel)
        main_layout.addWidget(self.button_box)

        self.setLayout(main_layout)

    def _connect_signals(self):
        self.add_line_button.clicked.connect(self._add_new_line)
        self.remove_line_button.clicked.connect(self._remove_selected_line)
        self.save_draft_button.clicked.connect(self.on_save_draft)
        self.save_post_button.clicked.connect(self.on_save_and_post)
        
        close_button = self.button_box.button(QDialogButtonBox.StandardButton.Close)
        cancel_button = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if close_button: # In view_only_mode
            close_button.clicked.connect(self.reject)
        if cancel_button: # In edit/new mode
            cancel_button.clicked.connect(self.reject)


    async def _load_initial_combo_data(self):
        # ... (same as previous version)
        try:
            if self.app_core.chart_of_accounts_manager:
                 self._accounts_cache = await self.app_core.chart_of_accounts_manager.get_accounts_for_selection(active_only=True)
            if self.app_core.tax_code_service:
                 self._tax_codes_cache = await self.app_core.tax_code_service.get_all()
            QMetaObject.invokeMethod(self, "_update_combos_in_all_lines_slot", Qt.ConnectionType.QueuedConnection)
        except Exception as e:
            self.app_core.logger.error(f"Error loading initial combo data for JE Dialog: {e}", exc_info=True)
            QMetaObject.invokeMethod(QMessageBox.staticMetaObject, "warning", Qt.ConnectionType.QueuedConnection,
                Q_ARG(QWidget, self), Q_ARG(str, "Data Load Error"), Q_ARG(str, f"Could not load all data for dropdowns: {e}"))

    @Slot()
    def _update_combos_in_all_lines_slot(self):
        # ... (same as previous version)
        for r in range(self.lines_table.rowCount()):
            line_data_to_use = None
            if self.existing_journal_entry_data_dict and r < len(self.existing_journal_entry_data_dict.get("lines",[])):
                line_data_to_use = self.existing_journal_entry_data_dict["lines"][r]
            self._populate_combos_for_row(r, line_data_to_use)

    async def _load_existing_journal_entry(self):
        # ... (same as previous version)
        if not self.journal_entry_id or not self.app_core.journal_entry_manager: return
        
        self.loaded_journal_entry_orm = await self.app_core.journal_entry_manager.get_journal_entry_for_dialog(self.journal_entry_id)
        if self.loaded_journal_entry_orm:
            json_data_str = self._serialize_je_for_ui(self.loaded_journal_entry_orm)
            QMetaObject.invokeMethod(self, "_populate_dialog_from_data_slot", Qt.ConnectionType.QueuedConnection,
                                     Q_ARG(str, json_data_str))
        else:
            QMetaObject.invokeMethod(QMessageBox.staticMetaObject, "warning", Qt.ConnectionType.QueuedConnection,
                Q_ARG(QWidget, self), Q_ARG(str, "Error"), Q_ARG(str, f"Journal Entry ID {self.journal_entry_id} not found."))
            self.reject()


    def _serialize_je_for_ui(self, je: JournalEntry) -> str: # Converts ORM to JSON string for cross-thread
        # ... (same as previous version)
        data = {
            "entry_date": je.entry_date, "journal_type": je.journal_type,
            "description": je.description, "reference": je.reference,
            "is_posted": je.is_posted, "source_type": je.source_type, "source_id": je.source_id,
            "lines": [
                { "account_id": line.account_id, "description": line.description,
                  "debit_amount": line.debit_amount, "credit_amount": line.credit_amount,
                  "currency_code": line.currency_code, "exchange_rate": line.exchange_rate,
                  "tax_code": line.tax_code, "tax_amount": line.tax_amount,
                  "dimension1_id": line.dimension1_id, "dimension2_id": line.dimension2_id,
                } for line in je.lines ]}
        return json.dumps(data, default=json_converter)

    @Slot(str)
    def _populate_dialog_from_data_slot(self, json_data_str: str): # Parses JSON and populates UI
        # ... (same as previous version, including read-only logic)
        try:
            data = json.loads(json_data_str, object_hook=json_date_hook)
            self.existing_journal_entry_data_dict = data 
        except json.JSONDecodeError:
            QMessageBox.critical(self, "Error", "Failed to parse existing journal entry data."); return

        if data.get("entry_date"): self.entry_date_edit.setDate(QDate(data["entry_date"]))
        type_idx = self.journal_type_combo.findText(data.get("journal_type", JournalTypeEnum.GENERAL.value))
        if type_idx != -1: self.journal_type_combo.setCurrentIndex(type_idx)
        self.description_edit.setText(data.get("description", ""))
        self.reference_edit.setText(data.get("reference", ""))

        self.lines_table.setRowCount(0) 
        for line_data_dict in data.get("lines", []): self._add_new_line(line_data_dict)
        if not data.get("lines") and not self.view_only_mode: self._add_new_line(); self._add_new_line()
        self._calculate_totals()

        is_read_only = self.view_only_mode or data.get("is_posted", False)
        if is_read_only:
            self.save_draft_button.setVisible(False) 
            self.save_post_button.setVisible(False)
            self.lines_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            
            # Iterate through form layout items to set read-only
            for i in range(self.header_form.rowCount()):
                label_item = self.header_form.itemAt(i, QFormLayout.ItemRole.LabelRole)
                field_item = self.header_form.itemAt(i, QFormLayout.ItemRole.FieldRole)
                if field_item:
                    widget = field_item.widget()
                    if isinstance(widget, (QLineEdit, QDateEdit)): widget.setReadOnly(True)
                    elif isinstance(widget, QComboBox): widget.setEnabled(False)
            
            self.add_line_button.setEnabled(False); self.remove_line_button.setEnabled(False)
            for r in range(self.lines_table.rowCount()): 
                del_btn_widget = self.lines_table.cellWidget(r, 6)
                if del_btn_widget : del_btn_widget.setVisible(False)


    def _populate_combos_for_row(self, row: int, line_data_for_this_row: Optional[Dict[str, Any]] = None):
        # ... (same as previous version, but ensure cast is imported)
        acc_combo = cast(QComboBox, self.lines_table.cellWidget(row, 0))
        if not acc_combo: acc_combo = QComboBox(); self.lines_table.setCellWidget(row, 0, acc_combo)
        acc_combo.clear()
        acc_combo.setEditable(True); acc_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        
        current_acc_id = line_data_for_this_row.get("account_id") if line_data_for_this_row else None
        selected_acc_idx = -1
        for i, acc_orm in enumerate(self._accounts_cache):
            acc_combo.addItem(f"{acc_orm.code} - {acc_orm.name}", acc_orm.id)
            if acc_orm.id == current_acc_id: selected_acc_idx = i
        
        if selected_acc_idx != -1: acc_combo.setCurrentIndex(selected_acc_idx)
        elif current_acc_id and self.loaded_journal_entry_orm: 
            orig_line_orm = next((l for l in self.loaded_journal_entry_orm.lines if l.account_id == current_acc_id), None)
            if orig_line_orm and orig_line_orm.account:
                acc_combo.addItem(f"{orig_line_orm.account.code} - {orig_line_orm.account.name} (Loaded)", current_acc_id) # Indicate it's from loaded data
                acc_combo.setCurrentIndex(acc_combo.count() -1)
            else: 
                acc_combo.addItem(f"ID: {current_acc_id} (Unknown/Not Found)", current_acc_id)
                acc_combo.setCurrentIndex(acc_combo.count() -1)
        elif current_acc_id : # If no ORM loaded but ID exists (e.g. error case)
             acc_combo.addItem(f"ID: {current_acc_id} (Not in cache)", current_acc_id)
             acc_combo.setCurrentIndex(acc_combo.count() -1)


        tax_combo = cast(QComboBox, self.lines_table.cellWidget(row, 4))
        if not tax_combo: tax_combo = QComboBox(); self.lines_table.setCellWidget(row, 4, tax_combo)
        tax_combo.clear()
        tax_combo.addItem("None", "") 
        current_tax_code_str = line_data_for_this_row.get("tax_code") if line_data_for_this_row else None
        selected_tax_idx = 0 
        for i, tc_orm in enumerate(self._tax_codes_cache):
            tax_combo.addItem(f"{tc_orm.code} ({tc_orm.rate}%)", tc_orm.code)
            if tc_orm.code == current_tax_code_str: selected_tax_idx = i + 1
        
        tax_combo.setCurrentIndex(selected_tax_idx)
        if selected_tax_idx == 0 and current_tax_code_str : # Loaded tax code not in cache
             tax_combo.addItem(f"{current_tax_code_str} (Not in cache)", current_tax_code_str)
             tax_combo.setCurrentIndex(tax_combo.count()-1)


    def _add_new_line(self, line_data: Optional[Dict[str, Any]] = None):
        # ... (same as previous, ensure icon path fallback)
        row_position = self.lines_table.rowCount()
        self.lines_table.insertRow(row_position)

        acc_combo = QComboBox(); self.lines_table.setCellWidget(row_position, 0, acc_combo)
        
        desc_item = QTableWidgetItem(line_data.get("description", "") if line_data else "")
        self.lines_table.setItem(row_position, 1, desc_item)

        debit_spin = QDoubleSpinBox(); debit_spin.setRange(0, 999999999999.99); debit_spin.setDecimals(2); debit_spin.setGroupSeparatorShown(True); debit_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        credit_spin = QDoubleSpinBox(); credit_spin.setRange(0, 999999999999.99); credit_spin.setDecimals(2); credit_spin.setGroupSeparatorShown(True); credit_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        if line_data:
            debit_spin.setValue(float(Decimal(str(line_data.get("debit_amount", "0")))))
            credit_spin.setValue(float(Decimal(str(line_data.get("credit_amount", "0")))))
        self.lines_table.setCellWidget(row_position, 2, debit_spin)
        self.lines_table.setCellWidget(row_position, 3, credit_spin)
        
        debit_spin.valueChanged.connect(lambda val, r=row_position, cs=credit_spin: cs.setValue(0.00) if val > 0.001 else None)
        credit_spin.valueChanged.connect(lambda val, r=row_position, ds=debit_spin: ds.setValue(0.00) if val > 0.001 else None)
        debit_spin.valueChanged.connect(self._calculate_totals_and_tax_for_row_slot(row_position))
        credit_spin.valueChanged.connect(self._calculate_totals_and_tax_for_row_slot(row_position))

        tax_combo = QComboBox(); self.lines_table.setCellWidget(row_position, 4, tax_combo)
        tax_combo.currentIndexChanged.connect(self._calculate_totals_and_tax_for_row_slot(row_position)) # Ensure it triggers recalc chain

        initial_tax_amt_str = "0.00"
        if line_data and line_data.get("tax_amount") is not None:
            initial_tax_amt_str = str(Decimal(str(line_data.get("tax_amount"))).quantize(Decimal("0.01")))
        tax_amt_item = QTableWidgetItem(initial_tax_amt_str)
        tax_amt_item.setFlags(tax_amt_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        tax_amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lines_table.setItem(row_position, 5, tax_amt_item)
        
        icon_path_prefix = "resources/icons/" 
        try: import app.resources_rc; icon_path_prefix = ":/icons/"
        except ImportError: pass
        del_button = QPushButton(QIcon(icon_path_prefix + "remove.svg"))
        del_button.setToolTip("Remove this line"); del_button.setFixedSize(24,24)
        del_button.clicked.connect(lambda _, r=row_position: self._remove_specific_line(r))
        self.lines_table.setCellWidget(row_position, 6, del_button)

        self._populate_combos_for_row(row_position, line_data) 
        self._recalculate_tax_for_line(row_position) 
        self._calculate_totals() 


    def _calculate_totals_and_tax_for_row_slot(self, row: int):
        # ... (same as previous)
        return lambda: self._chain_recalculate_tax_and_totals(row)

    def _chain_recalculate_tax_and_totals(self, row: int):
        # ... (same as previous)
        self._recalculate_tax_for_line(row)

    def _remove_selected_line(self):
        # ... (same as previous)
        current_row = self.lines_table.currentRow()
        if current_row >= 0: self._remove_specific_line(current_row)

    def _remove_specific_line(self, row_to_remove: int):
        # ... (same as previous)
        if self.view_only_mode or (self.loaded_journal_entry_orm and self.loaded_journal_entry_orm.is_posted): return
        if self.lines_table.rowCount() > 0 : 
            self.lines_table.removeRow(row_to_remove)
            self._calculate_totals()


    @Slot() 
    def _calculate_totals_from_signal(self): 
        # ... (same as previous)
        self._calculate_totals()

    def _calculate_totals(self):
        # ... (same as previous, ensure Decimal used)
        total_debits = Decimal(0); total_credits = Decimal(0)
        for row in range(self.lines_table.rowCount()):
            debit_spin = cast(QDoubleSpinBox, self.lines_table.cellWidget(row, 2))
            credit_spin = cast(QDoubleSpinBox, self.lines_table.cellWidget(row, 3))
            if debit_spin: total_debits += Decimal(str(debit_spin.value()))
            if credit_spin: total_credits += Decimal(str(credit_spin.value()))
        
        self.debits_label.setText(f"Debits: {total_debits:,.2f}")
        self.credits_label.setText(f"Credits: {total_credits:,.2f}")

        if abs(total_debits - total_credits) < Decimal("0.005"): 
            self.balance_label.setText("Balance: OK"); self.balance_label.setStyleSheet("font-weight: bold; color: green;")
        else:
            diff = total_debits - total_credits
            self.balance_label.setText(f"Balance: {diff:,.2f}"); self.balance_label.setStyleSheet("font-weight: bold; color: red;")

    def _recalculate_tax_for_line(self, row: int):
        # ... (same as previous, ensure Decimal used)
        try:
            debit_spin = cast(QDoubleSpinBox, self.lines_table.cellWidget(row, 2))
            credit_spin = cast(QDoubleSpinBox, self.lines_table.cellWidget(row, 3))
            tax_combo = cast(QComboBox, self.lines_table.cellWidget(row, 4))
            tax_amt_item = self.lines_table.item(row, 5)

            if not all([debit_spin, credit_spin, tax_combo]): return 
            if not tax_amt_item: 
                tax_amt_item = QTableWidgetItem("0.00")
                tax_amt_item.setFlags(tax_amt_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                tax_amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.lines_table.setItem(row, 5, tax_amt_item)

            base_amount = Decimal(str(debit_spin.value())) if debit_spin.value() > 0 else Decimal(str(credit_spin.value()))
            tax_code_str = tax_combo.currentData() if tax_combo.currentIndex() > 0 else None # Handles "None" item
            
            calculated_tax = Decimal(0)
            if tax_code_str and base_amount != Decimal(0):
                tc_obj = next((tc for tc in self._tax_codes_cache if tc.code == tax_code_str), None)
                if tc_obj and tc_obj.tax_type == "GST" and tc_obj.rate is not None:
                    tax_rate = tc_obj.rate / Decimal(100)
                    calculated_tax = (base_amount * tax_rate).quantize(Decimal("0.01"))
            
            tax_amt_item.setText(f"{calculated_tax:,.2f}")
        except Exception as e:
            self.app_core.logger.error(f"Error recalculating tax for row {row}: {e}", exc_info=True)
            if tax_amt_item: tax_amt_item.setText("Error")
        finally:
            self._calculate_totals() 


    def _collect_data(self) -> Optional[JournalEntryData]:
        # ... (same as previous, but ensure use of self.loaded_journal_entry_orm for source_type/id)
        lines_data: List[JournalEntryLineData] = []
        total_debits = Decimal(0); total_credits = Decimal(0)

        for row in range(self.lines_table.rowCount()):
            try:
                acc_combo = cast(QComboBox, self.lines_table.cellWidget(row, 0))
                desc_item_widget = self.lines_table.item(row, 1)
                debit_spin = cast(QDoubleSpinBox, self.lines_table.cellWidget(row, 2))
                credit_spin = cast(QDoubleSpinBox, self.lines_table.cellWidget(row, 3))
                tax_combo = cast(QComboBox, self.lines_table.cellWidget(row, 4))
                tax_amt_item_widget = self.lines_table.item(row, 5)

                account_id = acc_combo.currentData() if acc_combo else None
                line_debit = Decimal(str(debit_spin.value())) if debit_spin else Decimal(0)
                line_credit = Decimal(str(credit_spin.value())) if credit_spin else Decimal(0)

                if account_id is None and (line_debit != Decimal(0) or line_credit != Decimal(0)):
                    QMessageBox.warning(self, "Validation Error", f"Account not selected for line {row + 1} which has amounts.")
                    return None
                if account_id is None: continue 

                line_dto = JournalEntryLineData(
                    account_id=int(account_id),
                    description=desc_item_widget.text() if desc_item_widget else "",
                    debit_amount=line_debit, credit_amount=line_credit,
                    tax_code=tax_combo.currentData() if tax_combo and tax_combo.currentData() else None, 
                    tax_amount=Decimal(tax_amt_item_widget.text().replace(',', '')) if tax_amt_item_widget and tax_amt_item_widget.text() else Decimal(0),
                    currency_code="SGD", exchange_rate=Decimal(1), # Defaults for now
                    dimension1_id=None, dimension2_id=None 
                )
                lines_data.append(line_dto)
                total_debits += line_debit; total_credits += line_credit
            except Exception as e:
                QMessageBox.warning(self, "Input Error", f"Error processing line {row + 1}: {e}"); return None
        
        if not lines_data:
             QMessageBox.warning(self, "Input Error", "Journal entry must have at least one valid line."); return None
        if abs(total_debits - total_credits) > Decimal("0.01"):
            QMessageBox.warning(self, "Balance Error", f"Journal entry is not balanced. Debits: {total_debits:,.2f}, Credits: {total_credits:,.2f}."); return None

        try:
            # Get source_type/id from loaded ORM if editing, otherwise None for new.
            # self.loaded_journal_entry_orm is set in _load_existing_journal_entry
            source_type = self.loaded_journal_entry_orm.source_type if self.journal_entry_id and self.loaded_journal_entry_orm else None
            source_id = self.loaded_journal_entry_orm.source_id if self.journal_entry_id and self.loaded_journal_entry_orm else None
            
            entry_data = JournalEntryData(
                journal_type=self.journal_type_combo.currentText(),
                entry_date=self.entry_date_edit.date().toPython(),
                description=self.description_edit.text().strip() or None,
                reference=self.reference_edit.text().strip() or None,
                user_id=self.current_user_id, lines=lines_data,
                source_type=source_type, source_id=source_id
                # is_recurring, recurring_pattern_id are not set by this generic dialog directly.
            )
            return entry_data
        except ValueError as e: 
            QMessageBox.warning(self, "Validation Error", str(e)); return None

    @Slot()
    def on_save_draft(self):
        # ... (same as previous version)
        if self.view_only_mode or (self.loaded_journal_entry_orm and self.loaded_journal_entry_orm.is_posted):
            QMessageBox.information(self, "Info", "Cannot save. Entry is posted or in view-only mode.")
            return
        entry_data = self._collect_data()
        if entry_data: schedule_task_from_qt(self._perform_save(entry_data, post_after_save=False))

    @Slot()
    def on_save_and_post(self):
        # ... (same as previous version)
        if self.view_only_mode or (self.loaded_journal_entry_orm and self.loaded_journal_entry_orm.is_posted):
            QMessageBox.information(self, "Info", "Cannot save and post. Entry is already posted or in view-only mode.")
            return
        entry_data = self._collect_data()
        if entry_data: schedule_task_from_qt(self._perform_save(entry_data, post_after_save=True))

    async def _perform_save(self, entry_data: JournalEntryData, post_after_save: bool):
        # ... (same as previous version, ensuring Result type hint)
        manager = self.app_core.journal_entry_manager
        if not manager:
             QMetaObject.invokeMethod(QMessageBox.staticMetaObject, "critical", Qt.ConnectionType.QueuedConnection,
                Q_ARG(QWidget, self), Q_ARG(str, "Error"), Q_ARG(str, "Journal Entry Manager not available."))
             return

        result: Result[JournalEntry] # Explicit type hint
        if self.journal_entry_id and self.loaded_journal_entry_orm: 
            result = await manager.update_journal_entry(self.journal_entry_id, entry_data)
        else: 
            result = await manager.create_journal_entry(entry_data)

        if result.is_success:
            saved_je = result.value
            assert saved_je is not None
            if post_after_save:
                post_result: Result[JournalEntry] = await manager.post_journal_entry(saved_je.id, self.current_user_id)
                if post_result.is_success:
                    QMetaObject.invokeMethod(QMessageBox.staticMetaObject, "information", Qt.ConnectionType.QueuedConnection,
                        Q_ARG(QWidget, self), Q_ARG(str, "Success"), Q_ARG(str, "Journal entry saved and posted successfully."))
                    self.journal_entry_saved.emit(saved_je.id)
                    QMetaObject.invokeMethod(self, "accept", Qt.ConnectionType.QueuedConnection)
                else:
                    error_msg = f"Journal entry saved as draft (ID: {saved_je.id}), but failed to post:\n{', '.join(post_result.errors)}"
                    QMetaObject.invokeMethod(QMessageBox.staticMetaObject, "warning", Qt.ConnectionType.QueuedConnection,
                        Q_ARG(QWidget, self), Q_ARG(str, "Posting Error"), Q_ARG(str, error_msg))
                    self.journal_entry_saved.emit(saved_je.id) 
            else:
                QMetaObject.invokeMethod(QMessageBox.staticMetaObject, "information", Qt.ConnectionType.QueuedConnection,
                    Q_ARG(QWidget, self), Q_ARG(str, "Success"), Q_ARG(str, "Journal entry saved as draft successfully."))
                self.journal_entry_saved.emit(saved_je.id)
                QMetaObject.invokeMethod(self, "accept", Qt.ConnectionType.QueuedConnection)
        else:
            QMetaObject.invokeMethod(QMessageBox.staticMetaObject, "warning", Qt.ConnectionType.QueuedConnection,
                Q_ARG(QWidget, self), Q_ARG(str, "Save Error"), Q_ARG(str, f"Failed to save journal entry:\n{', '.join(result.errors)}"))


    def open(self) -> int: 
        # ... (same as previous version, with more thorough reset)
        if not self.journal_entry_id and not self.view_only_mode : 
            self.setWindowTitle("New Journal Entry") # Reset title
            self.entry_date_edit.setDate(QDate.currentDate()); self.entry_date_edit.setReadOnly(False)
            self.journal_type_combo.setCurrentText(JournalTypeEnum.GENERAL.value); self.journal_type_combo.setEnabled(True)
            self.description_edit.clear(); self.description_edit.setReadOnly(False)
            self.reference_edit.clear(); self.reference_edit.setReadOnly(False)
            self.lines_table.setRowCount(0)
            self._add_new_line()
            self._add_new_line()
            self._calculate_totals()
            self.save_draft_button.setVisible(True); self.save_draft_button.setEnabled(True)
            self.save_post_button.setVisible(True); self.save_post_button.setEnabled(True)
            self.save_post_button.setText("Save & Post")
            self.lines_table.setEditTriggers(QAbstractItemView.EditTrigger.AllEditTriggers)
            self.add_line_button.setEnabled(True); self.remove_line_button.setEnabled(True)
            
            # Ensure form layout fields are re-enabled
            for i in range(self.header_form.rowCount()):
                field_item = self.header_form.itemAt(i, QFormLayout.ItemRole.FieldRole)
                if field_item:
                    widget = field_item.widget()
                    if isinstance(widget, (QLineEdit, QDateEdit)): widget.setReadOnly(False)
                    elif isinstance(widget, QComboBox): widget.setEnabled(True)
            
            # Ensure line delete buttons are visible if any rows exist
            for r in range(self.lines_table.rowCount()):
                del_btn_widget = self.lines_table.cellWidget(r, 6)
                if del_btn_widget: del_btn_widget.setVisible(True)

        return super().open()
