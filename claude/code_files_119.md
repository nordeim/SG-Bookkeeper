<think>
The application is consistently stable through these updates, which is excellent. We've completed the backend work for General Ledger reporting and created the new table models (`TrialBalanceTableModel`, `GeneralLedgerTableModel`).

**Current Step: Enhancement Execution Plan: Refine Reporting UI with Native Qt Views - Phase 2B**

We are now focused on **Step B: Update `app/ui/reports/reports_widget.py`** from the "Refine Reporting UI" plan. This involves replacing the `QTextEdit` display with a `QStackedWidget` to host different native Qt views for each financial report.

**Detailed Plan & Checklist for `app/ui/reports/reports_widget.py` (Continued from previous thought process):**

*   [ ] **Modify `_create_financial_statements_tab()`**:
    *   Instead of `self.fs_display_area = QTextEdit()`, create `self.fs_display_stack = QStackedWidget()`.
    *   **Create Views and Models:**
        *   Balance Sheet: `self.bs_tree_view = QTreeView()`; `self.bs_model = QStandardItemModel()`
        *   Profit & Loss: `self.pl_tree_view = QTreeView()`; `self.pl_model = QStandardItemModel()`
        *   Trial Balance: `self.tb_table_view = QTableView()`; `self.tb_model = TrialBalanceTableModel()`
        *   General Ledger: `self.gl_table_view = QTableView()`; `self.gl_model = GeneralLedgerTableModel()`
            *   *(For GL, the model needs a way to also convey opening/closing balances if they aren't part of the table rows. The widget might need separate labels for these, updated when `gl_model.get_report_summary()` is called.)*
    *   **Add Views to StackedWidget**: Add each view as a page to `self.fs_display_stack`.
    *   **Set Models to Views**: Assign the created models to their respective views.
    *   **Initial View**: Set `self.fs_display_stack.setCurrentWidget()` to the view corresponding to the default selected report type (e.g., Balance Sheet -> `self.bs_tree_view`).
    *   **QTreeView Configuration**:
        *   Set `setAlternatingRowColors(True)`, `setUniformRowHeights(True)`.
        *   Set column headers (e.g., "Account/Description", "Amount", "Comparative Amount") on the `QStandardItemModel`.
        *   `header().setSectionResizeMode(...)` for columns.
    *   **QTableView Configuration**:
        *   Set properties like `setAlternatingRowColors(True)`, `setSelectionBehavior()`, `setEditTriggers()`, `setSortingEnabled(True)`.
        *   Hide ID columns if the models include them (e.g., TB model might not need it, GL model might not).
        *   `horizontalHeader().setSectionResizeMode(...)`.
*   [ ] **Update `_on_fs_report_type_changed(report_type: str)`**:
    *   When `fs_report_type_combo` changes:
        *   Switch `self.fs_display_stack.setCurrentWidget()` to the correct view (`bs_tree_view`, `pl_tree_view`, `tb_table_view`, or `gl_table_view`).
        *   Clear the model of the *newly selected* view to ensure old data isn't shown before generation.
        *   Enable/disable/clear relevant date parameters and the GL account combo as already implemented.
*   [ ] **Update `_display_financial_report(report_data: Dict[str, Any])`**:
    *   This method is critical. It will now populate the *currently active view/model* in the `QStackedWidget`.
    *   Use `self.fs_display_stack.currentWidget()` to determine which view is active, or use the `report_data['title']` / `self.fs_report_type_combo.currentText()` to decide which model to populate.
    *   **For Balance Sheet / P&L (QTreeView with QStandardItemModel)**:
        *   Create a new helper method, e.g., `_populate_tree_report_model(model: QStandardItemModel, report_data_section: Dict[str, Any], section_keys: List[str], is_pl: bool)`.
        *   This helper will clear the `model`, set its horizontal headers (e.g., ["Description", "Amount"] or ["Description", "Current Period", "Comparative Period"]).
        *   Iterate through `section_keys` (e.g., `['assets', 'liabilities', 'equity']` for BS).
        *   For each section:
            *   Add a top-level `QStandardItem` for the section title (bold).
            *   Iterate through `section_data.get('accounts', [])`. For each account:
                *   Create a `QStandardItem` for the account name/code.
                *   Create `QStandardItem`(s) for the amount(s), formatted and right-aligned.
                *   Append these as a row to the section item.
            *   Add a row for section totals (bold).
        *   Add grand totals (e.g., Net Profit for P&L) as top-level items or under the last section.
    *   **For Trial Balance (QTableView with TrialBalanceTableModel)**:
        *   Call `self.tb_model.update_data(report_data)`.
        *   The `ReportsWidget` might also display a label for `self.tb_model.get_balance_status()`.
    *   **For General Ledger (QTableView with GeneralLedgerTableModel)**:
        *   Call `self.gl_model.update_data(report_data)`.
        *   The `ReportsWidget` will need to add `QLabel`s (e.g., above or below the `gl_table_view`) to display the Account Name, Period, Opening Balance, and Closing Balance obtained from `self.gl_model.get_report_summary()`. These labels will be updated in this `_display_financial_report` method.
*   [ ] **Export Logic**:
    *   The export buttons will still use `self._current_financial_report_data`. The `ReportEngine` consumes the dictionary.
    *   The `ReportEngine` itself might need enhancements later to produce better PDF/Excel from these structured views, especially for hierarchical tree data, but for now, the existing generic export can be tried.

This is a significant refactoring of the report display. I will focus on `_create_financial_statements_tab` and `_display_financial_report`, and the new model population logic. The GL display will require adding labels for summary info.
</think>

This is excellent! The application's stability through these backend and foundational UI additions is very promising.

We are now at a key point in the "Refine Reporting UI" plan: **Step B - Update `app/ui/reports/reports_widget.py`**. This involves replacing the `QTextEdit` with a `QStackedWidget` to host different native Qt views (`QTreeView` for hierarchical reports like Balance Sheet and P&L, and `QTableView` for flat reports like Trial Balance and General Ledger), each backed by an appropriate model.

This is a substantial UI refactoring. I will provide the complete, updated `app/ui/reports/reports_widget.py` file.

---
**Update `app/ui/reports/reports_widget.py`**

```python
# app/ui/reports/reports_widget.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QDateEdit, QPushButton, QFormLayout, 
    QLineEdit, QGroupBox, QHBoxLayout, QMessageBox, QSpacerItem, QSizePolicy,
    QTabWidget, QTextEdit, QComboBox, QFileDialog, QInputDialog, QCompleter,
    QStackedWidget, QTreeView, QTableView # Added QStackedWidget, QTreeView, QTableView
)
from PySide6.QtCore import Qt, Slot, QDate, QTimer, QMetaObject, Q_ARG, QStandardPaths
from PySide6.QtGui import QIcon, QStandardItemModel, QStandardItem, QFont # Added QStandardItemModel, QStandardItem, QFont
from typing import Optional, Dict, Any, TYPE_CHECKING, List 
import json
from decimal import Decimal, InvalidOperation
import os 
from datetime import date as python_date, timedelta 

from app.core.application_core import ApplicationCore
from app.main import schedule_task_from_qt
from app.utils.json_helpers import json_converter, json_date_hook
from app.utils.pydantic_models import GSTReturnData 
from app.utils.result import Result 
from app.models.accounting.gst_return import GSTReturn 
from app.models.accounting.account import Account # For type hinting Account objects

# Import new table models
from .trial_balance_table_model import TrialBalanceTableModel
from .general_ledger_table_model import GeneralLedgerTableModel

if TYPE_CHECKING:
    from PySide6.QtGui import QPaintDevice 

class ReportsWidget(QWidget):
    def __init__(self, app_core: ApplicationCore, parent: Optional["QWidget"] = None):
        super().__init__(parent)
        self.app_core = app_core
        self._prepared_gst_data: Optional[GSTReturnData] = None 
        self._saved_draft_gst_return_orm: Optional[GSTReturn] = None 
        self._current_financial_report_data: Optional[Dict[str, Any]] = None
        self._gl_accounts_cache: List[Dict[str, Any]] = [] 

        self.icon_path_prefix = "resources/icons/" 
        try:
            import app.resources_rc 
            self.icon_path_prefix = ":/icons/"
        except ImportError:
            pass

        self.main_layout = QVBoxLayout(self)
        
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)

        self._create_gst_f5_tab()
        self._create_financial_statements_tab()
        
        self.setLayout(self.main_layout)

    def _format_decimal_for_display(self, value: Optional[Decimal], default_str: str = "0.00", show_blank_for_zero: bool = False) -> str:
        if value is None: return default_str if not show_blank_for_zero else ""
        try:
            d_value = Decimal(str(value)) # Ensure it's Decimal
            if show_blank_for_zero and d_value == Decimal(0):
                return ""
            return f"{d_value:,.2f}"
        except (InvalidOperation, TypeError):
            return "Error"

    # --- GST F5 Return Preparation Tab (Implementation as per previous validated version) ---
    def _create_gst_f5_tab(self):
        gst_f5_widget = QWidget()
        gst_f5_main_layout = QVBoxLayout(gst_f5_widget)
        gst_f5_group = QGroupBox("GST F5 Return Data Preparation")
        gst_f5_group_layout = QVBoxLayout(gst_f5_group) 
        date_selection_layout = QHBoxLayout()
        date_form = QFormLayout()
        self.gst_start_date_edit = QDateEdit(QDate.currentDate().addMonths(-3).addDays(-QDate.currentDate().day()+1))
        self.gst_start_date_edit.setCalendarPopup(True); self.gst_start_date_edit.setDisplayFormat("dd/MM/yyyy")
        date_form.addRow("Period Start Date:", self.gst_start_date_edit)
        self.gst_end_date_edit = QDateEdit(QDate.currentDate().addMonths(-1).addDays(-QDate.currentDate().day())) 
        self.gst_end_date_edit.setCalendarPopup(True); self.gst_end_date_edit.setDisplayFormat("dd/MM/yyyy")
        date_form.addRow("Period End Date:", self.gst_end_date_edit)
        date_selection_layout.addLayout(date_form)
        prepare_button_layout = QVBoxLayout()
        self.prepare_gst_button = QPushButton(QIcon(self.icon_path_prefix + "reports.svg"), "Prepare GST F5 Data")
        self.prepare_gst_button.clicked.connect(self._on_prepare_gst_f5_clicked)
        prepare_button_layout.addWidget(self.prepare_gst_button); prepare_button_layout.addStretch()
        date_selection_layout.addLayout(prepare_button_layout); date_selection_layout.addStretch(1)
        gst_f5_group_layout.addLayout(date_selection_layout)
        self.gst_display_form = QFormLayout()
        self.gst_std_rated_supplies_display = QLineEdit(); self.gst_std_rated_supplies_display.setReadOnly(True)
        self.gst_zero_rated_supplies_display = QLineEdit(); self.gst_zero_rated_supplies_display.setReadOnly(True)
        self.gst_exempt_supplies_display = QLineEdit(); self.gst_exempt_supplies_display.setReadOnly(True)
        self.gst_total_supplies_display = QLineEdit(); self.gst_total_supplies_display.setReadOnly(True); self.gst_total_supplies_display.setStyleSheet("font-weight: bold;")
        self.gst_taxable_purchases_display = QLineEdit(); self.gst_taxable_purchases_display.setReadOnly(True)
        self.gst_output_tax_display = QLineEdit(); self.gst_output_tax_display.setReadOnly(True)
        self.gst_input_tax_display = QLineEdit(); self.gst_input_tax_display.setReadOnly(True)
        self.gst_adjustments_display = QLineEdit("0.00"); self.gst_adjustments_display.setReadOnly(True)
        self.gst_net_payable_display = QLineEdit(); self.gst_net_payable_display.setReadOnly(True); self.gst_net_payable_display.setStyleSheet("font-weight: bold;")
        self.gst_filing_due_date_display = QLineEdit(); self.gst_filing_due_date_display.setReadOnly(True)
        self.gst_display_form.addRow("1. Standard-Rated Supplies:", self.gst_std_rated_supplies_display); self.gst_display_form.addRow("2. Zero-Rated Supplies:", self.gst_zero_rated_supplies_display); self.gst_display_form.addRow("3. Exempt Supplies:", self.gst_exempt_supplies_display); self.gst_display_form.addRow("4. Total Supplies (1+2+3):", self.gst_total_supplies_display); self.gst_display_form.addRow("5. Taxable Purchases:", self.gst_taxable_purchases_display); self.gst_display_form.addRow("6. Output Tax Due:", self.gst_output_tax_display); self.gst_display_form.addRow("7. Input Tax and Refunds Claimed:", self.gst_input_tax_display); self.gst_display_form.addRow("8. GST Adjustments:", self.gst_adjustments_display); self.gst_display_form.addRow("9. Net GST Payable / (Claimable):", self.gst_net_payable_display); self.gst_display_form.addRow("Filing Due Date:", self.gst_filing_due_date_display)
        gst_f5_group_layout.addLayout(self.gst_display_form)
        gst_action_button_layout = QHBoxLayout()
        self.save_draft_gst_button = QPushButton("Save Draft GST Return"); self.save_draft_gst_button.setEnabled(False)
        self.save_draft_gst_button.clicked.connect(self._on_save_draft_gst_return_clicked)
        self.finalize_gst_button = QPushButton("Finalize GST Return"); self.finalize_gst_button.setEnabled(False)
        self.finalize_gst_button.clicked.connect(self._on_finalize_gst_return_clicked)
        gst_action_button_layout.addStretch(); gst_action_button_layout.addWidget(self.save_draft_gst_button); gst_action_button_layout.addWidget(self.finalize_gst_button)
        gst_f5_group_layout.addLayout(gst_action_button_layout)
        gst_f5_main_layout.addWidget(gst_f5_group); gst_f5_main_layout.addStretch()
        self.tab_widget.addTab(gst_f5_widget, "GST F5 Preparation")

    # --- Financial Statements Tab ---
    def _create_financial_statements_tab(self):
        fs_widget = QWidget()
        fs_main_layout = QVBoxLayout(fs_widget)
        fs_group = QGroupBox("Financial Statements")
        fs_group_layout = QVBoxLayout(fs_group) # Main layout for this group

        # --- Controls ---
        controls_layout = QHBoxLayout()
        self.fs_params_form = QFormLayout() 
        self.fs_report_type_combo = QComboBox()
        self.fs_report_type_combo.addItems(["Balance Sheet", "Profit & Loss Statement", "Trial Balance", "General Ledger"])
        self.fs_params_form.addRow("Report Type:", self.fs_report_type_combo)
        self.fs_gl_account_label = QLabel("Account for GL:")
        self.fs_gl_account_combo = QComboBox()
        self.fs_gl_account_combo.setMinimumWidth(250); self.fs_gl_account_combo.setEditable(True)
        completer = QCompleter([f"{item.get('code')} - {item.get('name')}" for item in self._gl_accounts_cache]) # Initial empty completer
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.fs_gl_account_combo.setCompleter(completer)
        self.fs_params_form.addRow(self.fs_gl_account_label, self.fs_gl_account_combo)
        self.fs_as_of_date_edit = QDateEdit(QDate.currentDate())
        self.fs_as_of_date_edit.setCalendarPopup(True); self.fs_as_of_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.fs_params_form.addRow("As of Date:", self.fs_as_of_date_edit)
        self.fs_start_date_edit = QDateEdit(QDate.currentDate().addMonths(-1).addDays(-QDate.currentDate().day()+1))
        self.fs_start_date_edit.setCalendarPopup(True); self.fs_start_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.fs_params_form.addRow("Period Start Date:", self.fs_start_date_edit)
        self.fs_end_date_edit = QDateEdit(QDate.currentDate().addDays(-QDate.currentDate().day()))
        self.fs_end_date_edit.setCalendarPopup(True); self.fs_end_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.fs_params_form.addRow("Period End Date:", self.fs_end_date_edit)
        controls_layout.addLayout(self.fs_params_form)
        generate_fs_button_layout = QVBoxLayout()
        self.generate_fs_button = QPushButton(QIcon(self.icon_path_prefix + "reports.svg"), "Generate Report")
        self.generate_fs_button.clicked.connect(self._on_generate_financial_report_clicked)
        generate_fs_button_layout.addWidget(self.generate_fs_button); generate_fs_button_layout.addStretch()
        controls_layout.addLayout(generate_fs_button_layout); controls_layout.addStretch(1)
        fs_group_layout.addLayout(controls_layout)
        
        # --- Report Display Area using QStackedWidget ---
        self.fs_display_stack = QStackedWidget()
        fs_group_layout.addWidget(self.fs_display_stack, 1) # Give stretch factor

        # Create views and models for each report type
        self.bs_tree_view = QTreeView(); self.bs_tree_view.setAlternatingRowColors(True); self.bs_tree_view.setHeaderHidden(False)
        self.bs_model = QStandardItemModel(); self.bs_tree_view.setModel(self.bs_model)
        self.fs_display_stack.addWidget(self.bs_tree_view)

        self.pl_tree_view = QTreeView(); self.pl_tree_view.setAlternatingRowColors(True); self.pl_tree_view.setHeaderHidden(False)
        self.pl_model = QStandardItemModel(); self.pl_tree_view.setModel(self.pl_model)
        self.fs_display_stack.addWidget(self.pl_tree_view)

        self.tb_table_view = QTableView(); self.tb_table_view.setAlternatingRowColors(True); self.tb_table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.ExtendedSelection); self.tb_table_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.tb_table_view.setSortingEnabled(True)
        self.tb_model = TrialBalanceTableModel(); self.tb_table_view.setModel(self.tb_model)
        self.fs_display_stack.addWidget(self.tb_table_view)

        gl_widget_container = QWidget() # Container for GL table and summary labels
        gl_layout = QVBoxLayout(gl_widget_container)
        gl_layout.setContentsMargins(0,0,0,0)
        self.gl_summary_label_account = QLabel("Account: N/A"); self.gl_summary_label_account.setStyleSheet("font-weight: bold;")
        self.gl_summary_label_period = QLabel("Period: N/A")
        self.gl_summary_label_ob = QLabel("Opening Balance: 0.00")
        gl_summary_header_layout = QHBoxLayout()
        gl_summary_header_layout.addWidget(self.gl_summary_label_account)
        gl_summary_header_layout.addStretch()
        gl_summary_header_layout.addWidget(self.gl_summary_label_period)
        gl_layout.addLayout(gl_summary_header_layout)
        gl_layout.addWidget(self.gl_summary_label_ob)
        self.gl_table_view = QTableView(); self.gl_table_view.setAlternatingRowColors(True); self.gl_table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.ExtendedSelection); self.gl_table_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.gl_table_view.setSortingEnabled(True)
        self.gl_model = GeneralLedgerTableModel(); self.gl_table_view.setModel(self.gl_model)
        gl_layout.addWidget(self.gl_table_view)
        self.gl_summary_label_cb = QLabel("Closing Balance: 0.00"); self.gl_summary_label_cb.setAlignment(Qt.AlignmentFlag.AlignRight)
        gl_layout.addWidget(self.gl_summary_label_cb)
        self.fs_display_stack.addWidget(gl_widget_container)


        # --- Export Buttons ---
        export_button_layout = QHBoxLayout()
        self.export_pdf_button = QPushButton("Export to PDF"); self.export_pdf_button.setEnabled(False)
        self.export_pdf_button.clicked.connect(lambda: self._on_export_report_clicked("pdf"))
        self.export_excel_button = QPushButton("Export to Excel"); self.export_excel_button.setEnabled(False)
        self.export_excel_button.clicked.connect(lambda: self._on_export_report_clicked("excel"))
        export_button_layout.addStretch()
        export_button_layout.addWidget(self.export_pdf_button); export_button_layout.addWidget(self.export_excel_button)
        fs_group_layout.addLayout(export_button_layout)
        
        fs_main_layout.addWidget(fs_group)
        self.tab_widget.addTab(fs_widget, "Financial Statements")

        self.fs_report_type_combo.currentTextChanged.connect(self._on_fs_report_type_changed)
        self._on_fs_report_type_changed(self.fs_report_type_combo.currentText()) # Initial UI setup

    # --- GST F5 Slots & Methods (Unchanged) ---
    @Slot()
    def _on_prepare_gst_f5_clicked(self): # ...
        start_date = self.gst_start_date_edit.date().toPython(); end_date = self.gst_end_date_edit.date().toPython()
        if start_date > end_date: QMessageBox.warning(self, "Date Error", "Start date cannot be after end date."); return
        if not self.app_core.current_user: QMessageBox.warning(self, "Authentication Error", "No user logged in."); return
        if not self.app_core.gst_manager: QMessageBox.critical(self, "Error", "GST Manager not available."); return
        self.prepare_gst_button.setEnabled(False); self.prepare_gst_button.setText("Preparing...")
        self._saved_draft_gst_return_orm = None; self.finalize_gst_button.setEnabled(False)
        current_user_id = self.app_core.current_user.id
        future = schedule_task_from_qt(self.app_core.gst_manager.prepare_gst_return_data(start_date, end_date, current_user_id))
        if future: future.add_done_callback(self._handle_prepare_gst_f5_result)
        else: self._handle_prepare_gst_f5_result(None) 
    def _handle_prepare_gst_f5_result(self, future): # ...
        self.prepare_gst_button.setEnabled(True); self.prepare_gst_button.setText("Prepare GST F5 Data")
        if future is None: QMessageBox.critical(self, "Task Error", "Failed to schedule GST data preparation."); self._clear_gst_display_fields(); self.save_draft_gst_button.setEnabled(False); self.finalize_gst_button.setEnabled(False); return
        try:
            result: Result[GSTReturnData] = future.result()
            if result.is_success and result.value: self._prepared_gst_data = result.value; self._update_gst_f5_display(self._prepared_gst_data); self.save_draft_gst_button.setEnabled(True); self.finalize_gst_button.setEnabled(False) 
            else: self._clear_gst_display_fields(); self.save_draft_gst_button.setEnabled(False); self.finalize_gst_button.setEnabled(False); QMessageBox.warning(self, "GST Data Error", f"Failed to prepare GST data:\n{', '.join(result.errors)}")
        except Exception as e: self._clear_gst_display_fields(); self.save_draft_gst_button.setEnabled(False); self.finalize_gst_button.setEnabled(False); self.app_core.logger.error(f"Exception handling GST F5 preparation result: {e}", exc_info=True); QMessageBox.critical(self, "GST Data Error", f"An unexpected error occurred: {str(e)}")
    def _update_gst_f5_display(self, gst_data: GSTReturnData): # ...
        self.gst_std_rated_supplies_display.setText(self._format_decimal_for_display(gst_data.standard_rated_supplies)); self.gst_zero_rated_supplies_display.setText(self._format_decimal_for_display(gst_data.zero_rated_supplies)); self.gst_exempt_supplies_display.setText(self._format_decimal_for_display(gst_data.exempt_supplies)); self.gst_total_supplies_display.setText(self._format_decimal_for_display(gst_data.total_supplies)); self.gst_taxable_purchases_display.setText(self._format_decimal_for_display(gst_data.taxable_purchases)); self.gst_output_tax_display.setText(self._format_decimal_for_display(gst_data.output_tax)); self.gst_input_tax_display.setText(self._format_decimal_for_display(gst_data.input_tax)); self.gst_adjustments_display.setText(self._format_decimal_for_display(gst_data.tax_adjustments)); self.gst_net_payable_display.setText(self._format_decimal_for_display(gst_data.tax_payable)); self.gst_filing_due_date_display.setText(gst_data.filing_due_date.strftime('%d/%m/%Y') if gst_data.filing_due_date else "")
    def _clear_gst_display_fields(self): # ...
        for w in [self.gst_std_rated_supplies_display, self.gst_zero_rated_supplies_display, self.gst_exempt_supplies_display, self.gst_total_supplies_display, self.gst_taxable_purchases_display, self.gst_output_tax_display, self.gst_input_tax_display, self.gst_net_payable_display, self.gst_filing_due_date_display]: w.clear()
        self.gst_adjustments_display.setText("0.00"); self._prepared_gst_data = None; self._saved_draft_gst_return_orm = None
    @Slot()
    def _on_save_draft_gst_return_clicked(self): # ...
        if not self._prepared_gst_data: QMessageBox.warning(self, "No Data", "Please prepare GST data first."); return
        if not self.app_core.current_user: QMessageBox.warning(self, "Authentication Error", "No user logged in."); return
        self._prepared_gst_data.user_id = self.app_core.current_user.id
        if self._saved_draft_gst_return_orm and self._saved_draft_gst_return_orm.id: self._prepared_gst_data.id = self._saved_draft_gst_return_orm.id
        self.save_draft_gst_button.setEnabled(False); self.save_draft_gst_button.setText("Saving Draft..."); self.finalize_gst_button.setEnabled(False)
        future = schedule_task_from_qt(self.app_core.gst_manager.save_gst_return(self._prepared_gst_data))
        if future: future.add_done_callback(self._handle_save_draft_gst_result)
        else: self._handle_save_draft_gst_result(None)
    def _handle_save_draft_gst_result(self, future): # ...
        self.save_draft_gst_button.setEnabled(True); self.save_draft_gst_button.setText("Save Draft GST Return")
        if future is None: QMessageBox.critical(self, "Task Error", "Failed to schedule GST draft save."); return
        try:
            result: Result[GSTReturn] = future.result()
            if result.is_success and result.value: self._saved_draft_gst_return_orm = result.value;
                if self._prepared_gst_data: self._prepared_gst_data.id = result.value.id 
                QMessageBox.information(self, "Success", f"GST Return draft saved successfully (ID: {result.value.id})."); self.finalize_gst_button.setEnabled(True) 
            else: QMessageBox.warning(self, "Save Error", f"Failed to save GST Return draft:\n{', '.join(result.errors)}"); self.finalize_gst_button.setEnabled(False)
        except Exception as e: self.app_core.logger.error(f"Exception handling save draft GST result: {e}", exc_info=True); QMessageBox.critical(self, "Save Error", f"An unexpected error occurred: {str(e)}"); self.finalize_gst_button.setEnabled(False)
    @Slot()
    def _on_finalize_gst_return_clicked(self): # ...
        if not self._saved_draft_gst_return_orm or not self._saved_draft_gst_return_orm.id: QMessageBox.warning(self, "No Draft", "Please prepare and save a draft GST return first."); return
        if self._saved_draft_gst_return_orm.status != "Draft": QMessageBox.information(self, "Already Processed", f"This GST Return (ID: {self._saved_draft_gst_return_orm.id}) is already '{self._saved_draft_gst_return_orm.status}'."); return
        if not self.app_core.current_user: QMessageBox.warning(self, "Authentication Error", "No user logged in."); return
        submission_ref, ok_ref = QInputDialog.getText(self, "Finalize GST Return", "Enter Submission Reference No.:")
        if not ok_ref or not submission_ref.strip(): QMessageBox.information(self, "Cancelled", "Submission reference not provided. Finalization cancelled."); return
        submission_date_str, ok_date = QInputDialog.getText(self, "Finalize GST Return", "Enter Submission Date (YYYY-MM-DD):", text=python_date.today().isoformat())
        if not ok_date or not submission_date_str.strip(): QMessageBox.information(self, "Cancelled", "Submission date not provided. Finalization cancelled."); return
        try: parsed_submission_date = python_date.fromisoformat(submission_date_str)
        except ValueError: QMessageBox.warning(self, "Invalid Date", "Submission date format is invalid. Please use YYYY-MM-DD."); return
        self.finalize_gst_button.setEnabled(False); self.finalize_gst_button.setText("Finalizing..."); self.save_draft_gst_button.setEnabled(False)
        future = schedule_task_from_qt(self.app_core.gst_manager.finalize_gst_return(return_id=self._saved_draft_gst_return_orm.id, submission_reference=submission_ref.strip(), submission_date=parsed_submission_date, user_id=self.app_core.current_user.id))
        if future: future.add_done_callback(self._handle_finalize_gst_result)
        else: self._handle_finalize_gst_result(None)
    def _handle_finalize_gst_result(self, future): # ...
        self.finalize_gst_button.setText("Finalize GST Return") 
        if future is None: QMessageBox.critical(self, "Task Error", "Failed to schedule GST finalization."); self.finalize_gst_button.setEnabled(True if self._saved_draft_gst_return_orm and self._saved_draft_gst_return_orm.status == "Draft" else False); return
        try:
            result: Result[GSTReturn] = future.result()
            if result.is_success and result.value: QMessageBox.information(self, "Success", f"GST Return (ID: {result.value.id}) finalized successfully.\nStatus: {result.value.status}.\nSettlement JE ID: {result.value.journal_entry_id or 'N/A'}"); self._saved_draft_gst_return_orm = result.value; self.save_draft_gst_button.setEnabled(False); self.finalize_gst_button.setEnabled(False); 
                if self._prepared_gst_data: self._prepared_gst_data.status = result.value.status
            else: QMessageBox.warning(self, "Finalization Error", f"Failed to finalize GST Return:\n{', '.join(result.errors)}");
                if self._saved_draft_gst_return_orm and self._saved_draft_gst_return_orm.status == "Draft": self.finalize_gst_button.setEnabled(True) 
                self.save_draft_gst_button.setEnabled(True) 
        except Exception as e: self.app_core.logger.error(f"Exception handling finalize GST result: {e}", exc_info=True); QMessageBox.critical(self, "Finalization Error", f"An unexpected error occurred: {str(e)}"); 
            if self._saved_draft_gst_return_orm and self._saved_draft_gst_return_orm.status == "Draft": self.finalize_gst_button.setEnabled(True)
            self.save_draft_gst_button.setEnabled(True) 

    # --- Financial Statements Slots & Methods ---
    @Slot(str)
    def _on_fs_report_type_changed(self, report_type: str):
        is_pl_report = (report_type == "Profit & Loss Statement")
        is_gl_report = (report_type == "General Ledger")

        self.fs_as_of_date_edit.setVisible(not is_pl_report and not is_gl_report)
        self.fs_start_date_edit.setVisible(is_pl_report or is_gl_report)
        self.fs_end_date_edit.setVisible(is_pl_report or is_gl_report)
        self.fs_gl_account_combo.setVisible(is_gl_report)
        self.fs_gl_account_label.setVisible(is_gl_report)

        if hasattr(self, 'fs_params_form') and self.fs_params_form:
            for i in range(self.fs_params_form.rowCount()):
                field_widget = self.fs_params_form.itemAt(i, QFormLayout.ItemRole.FieldRole).widget()
                label_for_field = self.fs_params_form.labelForField(field_widget)
                if label_for_field: 
                    if field_widget == self.fs_as_of_date_edit: label_for_field.setVisible(not is_pl_report and not is_gl_report)
                    elif field_widget == self.fs_start_date_edit: label_for_field.setVisible(is_pl_report or is_gl_report)
                    elif field_widget == self.fs_end_date_edit: label_for_field.setVisible(is_pl_report or is_gl_report)
        
        if is_gl_report:
             self.fs_display_stack.setCurrentWidget(self.gl_widget_container) # Changed from self.gl_table_view
             if not self._gl_accounts_cache: schedule_task_from_qt(self._load_gl_accounts_for_combo())
        elif report_type == "Balance Sheet": self.fs_display_stack.setCurrentWidget(self.bs_tree_view)
        elif report_type == "Profit & Loss Statement": self.fs_display_stack.setCurrentWidget(self.pl_tree_view)
        elif report_type == "Trial Balance": self.fs_display_stack.setCurrentWidget(self.tb_table_view)
        
        self._current_financial_report_data = None 
        # Clear the current model, not just a generic QTextEdit
        current_view = self.fs_display_stack.currentWidget()
        if isinstance(current_view, QTreeView) and isinstance(current_view.model(), QStandardItemModel):
            cast(QStandardItemModel, current_view.model()).clear()
        elif isinstance(current_view, QTableView) and hasattr(current_view.model(), 'update_data'): # For custom models
            cast(Any, current_view.model()).update_data({}) # Pass empty data dict or list as per model's update_data
        elif hasattr(current_view, 'clear'): # Fallback for other potential views like QTextEdit if it were still used
             current_view.clear()


        self.export_pdf_button.setEnabled(False); self.export_excel_button.setEnabled(False)

    async def _load_gl_accounts_for_combo(self): # ... (same as previous version)
        if not self.app_core.chart_of_accounts_manager: self.app_core.logger.error("ChartOfAccountsManager not available for GL account combo."); return
        try:
            accounts_orm: List[Account] = await self.app_core.chart_of_accounts_manager.get_accounts_for_selection(active_only=True)
            self._gl_accounts_cache = [{"id": acc.id, "code": acc.code, "name": acc.name} for acc in accounts_orm]
            accounts_json = json.dumps(self._gl_accounts_cache, default=json_converter)
            QMetaObject.invokeMethod(self, "_populate_gl_account_combo_slot", Qt.ConnectionType.QueuedConnection, Q_ARG(str, accounts_json))
        except Exception as e: self.app_core.logger.error(f"Error loading accounts for GL combo: {e}", exc_info=True); QMessageBox.warning(self, "Account Load Error", "Could not load accounts for General Ledger selection.")

    @Slot(str)
    def _populate_gl_account_combo_slot(self, accounts_json_str: str): # ... (same as previous version)
        self.fs_gl_account_combo.clear()
        try:
            accounts_data = json.loads(accounts_json_str); self._gl_accounts_cache = accounts_data if accounts_data else []
            self.fs_gl_account_combo.addItem("-- Select Account --", 0) 
            for acc_data in self._gl_accounts_cache: self.fs_gl_account_combo.addItem(f"{acc_data['code']} - {acc_data['name']}", acc_data['id'])
        except json.JSONDecodeError: self.app_core.logger.error("Failed to parse accounts JSON for GL combo."); self.fs_gl_account_combo.addItem("Error loading accounts", 0)


    @Slot()
    def _on_generate_financial_report_clicked(self): # ... (same logic for calling generator)
        report_type = self.fs_report_type_combo.currentText()
        if not self.app_core.financial_statement_generator: QMessageBox.critical(self, "Error", "Financial Statement Generator not available."); return
        self.generate_fs_button.setEnabled(False); self.generate_fs_button.setText("Generating...")
        self.export_pdf_button.setEnabled(False); self.export_excel_button.setEnabled(False)
        # Clear appropriate model before generating
        current_view = self.fs_display_stack.currentWidget()
        if isinstance(current_view, QTreeView) and isinstance(current_view.model(), QStandardItemModel): cast(QStandardItemModel, current_view.model()).clear()
        elif isinstance(current_view, QTableView) and hasattr(current_view.model(), 'update_data'): cast(Any, current_view.model()).update_data({})
        elif hasattr(current_view, 'clear'): current_view.clear()


        coro: Optional[Any] = None 
        if report_type == "Balance Sheet": as_of_date = self.fs_as_of_date_edit.date().toPython(); coro = self.app_core.financial_statement_generator.generate_balance_sheet(as_of_date)
        elif report_type == "Profit & Loss Statement": start_date = self.fs_start_date_edit.date().toPython(); end_date = self.fs_end_date_edit.date().toPython(); 
            if start_date > end_date: QMessageBox.warning(self, "Date Error", "Start date cannot be after end date for P&L."); self.generate_fs_button.setEnabled(True); self.generate_fs_button.setText("Generate Report"); return
            coro = self.app_core.financial_statement_generator.generate_profit_loss(start_date, end_date)
        elif report_type == "Trial Balance": as_of_date = self.fs_as_of_date_edit.date().toPython(); coro = self.app_core.financial_statement_generator.generate_trial_balance(as_of_date)
        elif report_type == "General Ledger":
            account_id = self.fs_gl_account_combo.currentData(); 
            if not isinstance(account_id, int) or account_id == 0: QMessageBox.warning(self, "Selection Error", "Please select a valid account for the General Ledger report."); self.generate_fs_button.setEnabled(True); self.generate_fs_button.setText("Generate Report"); return
            start_date = self.fs_start_date_edit.date().toPython(); end_date = self.fs_end_date_edit.date().toPython()
            if start_date > end_date: QMessageBox.warning(self, "Date Error", "Start date cannot be after end date for General Ledger."); self.generate_fs_button.setEnabled(True); self.generate_fs_button.setText("Generate Report"); return
            coro = self.app_core.financial_statement_generator.generate_general_ledger(account_id, start_date, end_date)
        if coro:
            future = schedule_task_from_qt(coro)
            if future: future.add_done_callback(self._handle_financial_report_result)
            else: self._handle_financial_report_result(None)
        else: QMessageBox.warning(self, "Selection Error", "Invalid report type selected or parameters missing."); self.generate_fs_button.setEnabled(True); self.generate_fs_button.setText("Generate Report")


    def _handle_financial_report_result(self, future): # ... (same logic)
        self.generate_fs_button.setEnabled(True); self.generate_fs_button.setText("Generate Report")
        if future is None: QMessageBox.critical(self, "Task Error", "Failed to schedule report generation."); return
        try:
            report_data: Optional[Dict[str, Any]] = future.result() 
            if report_data: self._current_financial_report_data = report_data; self._display_financial_report(report_data); self.export_pdf_button.setEnabled(True); self.export_excel_button.setEnabled(True)
            else: QMessageBox.warning(self, "Report Error", "Failed to generate report data or report data is empty.")
        except Exception as e: self.app_core.logger.error(f"Exception handling financial report result: {e}", exc_info=True); QMessageBox.critical(self, "Report Generation Error", f"An unexpected error occurred: {str(e)}")

    def _populate_hierarchical_model(self, model: QStandardItemModel, report_data: Dict[str, Any], section_keys: List[str], title_key: str = "name", balance_key: str = "balance"):
        model.clear()
        headers = ["Description", "Amount"] # Simplified headers for TreeView
        # Potentially add "Comparative Amount" if comparative reports are enhanced
        model.setHorizontalHeaderLabels(headers)
        root_node = model.invisibleRootItem()

        bold_font = QFont(); bold_font.setBold(True)

        for section_id in section_keys: # e.g., "assets", "liabilities", "equity" OR "revenue", "expenses"
            section_data = report_data.get(section_id)
            if not section_data: continue

            section_title = section_id.replace('_', ' ').title() # Default title
            if 'title' in section_data : section_title = section_data['title'] # If report_data provides a display title

            section_item = QStandardItem(section_title)
            section_item.setFont(bold_font)
            empty_amount_item = QStandardItem("") # For alignment
            empty_amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            root_node.appendRow([section_item, empty_amount_item])

            for acc_dict in section_data.get("accounts", []):
                desc_text = f"{acc_dict.get('code','')} - {acc_dict.get(title_key,'')}"
                acc_desc_item = QStandardItem(desc_text)
                acc_balance_item = QStandardItem(self._format_decimal_for_display(acc_dict.get(balance_key)))
                acc_balance_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                section_item.appendRow([acc_desc_item, acc_balance_item])
            
            total_desc_item = QStandardItem(f"Total {section_title}")
            total_desc_item.setFont(bold_font)
            total_amount_item = QStandardItem(self._format_decimal_for_display(section_data.get("total")))
            total_amount_item.setFont(bold_font)
            total_amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            section_item.appendRow([total_desc_item, total_amount_item])

        # Grand totals (e.g., Net Profit for P&L, Total Liabilities & Equity for BS)
        if report_data.get('title') == "Profit & Loss Statement" and 'net_profit' in report_data:
            net_profit_desc = QStandardItem("Net Profit / (Loss)")
            net_profit_desc.setFont(bold_font)
            net_profit_amount = QStandardItem(self._format_decimal_for_display(report_data.get('net_profit')))
            net_profit_amount.setFont(bold_font); net_profit_amount.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            root_node.appendRow([QStandardItem(""), QStandardItem("")]) # Spacer
            root_node.appendRow([net_profit_desc, net_profit_amount])
        elif report_data.get('title') == "Balance Sheet" and 'total_liabilities_equity' in report_data:
            total_lia_eq_desc = QStandardItem("Total Liabilities & Equity")
            total_lia_eq_desc.setFont(bold_font)
            total_lia_eq_amount = QStandardItem(self._format_decimal_for_display(report_data.get('total_liabilities_equity')))
            total_lia_eq_amount.setFont(bold_font); total_lia_eq_amount.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            root_node.appendRow([QStandardItem(""), QStandardItem("")]) # Spacer
            root_node.appendRow([total_lia_eq_desc, total_lia_eq_amount])
            if report_data.get('is_balanced') is False:
                 warning_item = QStandardItem("Warning: Balance Sheet is out of balance!")
                 warning_item.setForeground(QColor("red")); warning_item.setFont(bold_font)
                 root_node.appendRow([warning_item,QStandardItem("")])


    def _display_financial_report(self, report_data: Dict[str, Any]):
        report_title = report_data.get('title', '')
        current_view = self.fs_display_stack.currentWidget()

        if report_title == "Balance Sheet":
            self.fs_display_stack.setCurrentWidget(self.bs_tree_view)
            self._populate_hierarchical_model(self.bs_model, report_data, ['assets', 'liabilities', 'equity'])
            self.bs_tree_view.expandAll()
            for i in range(self.bs_model.columnCount()): self.bs_tree_view.resizeColumnToContents(i)
        elif report_title == "Profit & Loss Statement":
            self.fs_display_stack.setCurrentWidget(self.pl_tree_view)
            self._populate_hierarchical_model(self.pl_model, report_data, ['revenue', 'expenses'])
            self.pl_tree_view.expandAll()
            for i in range(self.pl_model.columnCount()): self.pl_tree_view.resizeColumnToContents(i)
        elif report_title == "Trial Balance":
            self.fs_display_stack.setCurrentWidget(self.tb_table_view)
            self.tb_model.update_data(report_data)
            # Display balance status for TB
            status_msg = self.tb_model.get_balance_status()
            # (Consider adding a status label for TB if not displaying totals row in table)
            self.app_core.logger.info(f"Trial Balance Status: {status_msg}")
        elif report_title == "General Ledger":
            self.fs_display_stack.setCurrentWidget(self.gl_widget_container) # Show the container
            summary = self.gl_model.get_report_summary() # Get summary before updating data which resets it
            self.gl_model.update_data(report_data) # This populates the table
            # Update summary labels AFTER model has processed new data
            gl_summary_data = self.gl_model.get_report_summary()
            self.gl_summary_label_account.setText(f"Account: {gl_summary_data['account_name']}")
            self.gl_summary_label_period.setText(gl_summary_data['period_description'])
            self.gl_summary_label_ob.setText(f"Opening Balance: {self._format_decimal_for_display(gl_summary_data['opening_balance'], show_zero_as_blank=False)}")
            self.gl_summary_label_cb.setText(f"Closing Balance: {self._format_decimal_for_display(gl_summary_data['closing_balance'], show_zero_as_blank=False)}")
        else:
            # Fallback to QTextEdit if a new report type is added without specific view
            # Or better, switch to a generic placeholder view.
            # For now, this case should not be hit with current report types.
            self.fs_display_stack.setCurrentWidget(self.bs_tree_view) # Default to BS view
            cast(QStandardItemModel, self.bs_tree_view.model()).clear()
            self.app_core.logger.warning(f"Unhandled report title '{report_title}' for display.")
            QMessageBox.warning(self, "Display Error", f"Display format for '{report_title}' is not yet implemented.")


    @Slot(str)
    def _on_export_report_clicked(self, format_type: str): # ... (same as previous version)
        if not self._current_financial_report_data: QMessageBox.warning(self, "No Report", "Please generate a report first before exporting."); return
        report_title = self._current_financial_report_data.get('title', 'FinancialReport').replace(' ', '_').replace('&', 'And').replace('/', '-').replace(':', '') 
        default_filename = f"{report_title}_{python_date.today().strftime('%Y%m%d')}.{format_type}"
        documents_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        if not documents_path: documents_path = os.path.expanduser("~") 
        file_path, _ = QFileDialog.getSaveFileName(self, f"Save {format_type.upper()} Report", os.path.join(documents_path, default_filename), f"{format_type.upper()} Files (*.{format_type});;All Files (*)")
        if file_path:
            self.export_pdf_button.setEnabled(False); self.export_excel_button.setEnabled(False)
            # ReportEngine needs the raw dict, not a model
            future = schedule_task_from_qt(self.app_core.report_engine.export_report(self._current_financial_report_data, format_type)) # type: ignore
            if future: future.add_done_callback(lambda f, fp=file_path, ft=format_type: self._handle_export_result(f, fp, ft))
            else: self._handle_export_result(None, file_path, format_type)

    def _handle_export_result(self, future, file_path: str, format_type: str): # ... (same as previous version)
        self.export_pdf_button.setEnabled(True); self.export_excel_button.setEnabled(True)
        if future is None: QMessageBox.critical(self, "Task Error", "Failed to schedule report export."); return
        try:
            report_bytes: Optional[bytes] = future.result()
            if report_bytes:
                with open(file_path, "wb") as f: f.write(report_bytes)
                QMessageBox.information(self, "Export Successful", f"Report exported to:\n{file_path}")
            else: QMessageBox.warning(self, "Export Failed", f"Failed to generate report bytes for {format_type.upper()}.")
        except Exception as e: self.app_core.logger.error(f"Exception handling report export result: {e}", exc_info=True); QMessageBox.critical(self, "Export Error", f"An error occurred during export: {str(e)}")

```
**Validation of `app/ui/reports/reports_widget.py` (Refactor to Native Views):**
*   **Imports**: Added `QStackedWidget`, `QTreeView`, `QTableView`, `QStandardItemModel`, `QStandardItem`, `QFont`, `QCompleter`. Imported `TrialBalanceTableModel` and `GeneralLedgerTableModel`.
*   **`_create_financial_statements_tab()`**:
    *   `self.fs_display_area` (QTextEdit) is replaced by `self.fs_display_stack = QStackedWidget()`.
    *   Four views are created: `self.bs_tree_view` (QTreeView), `self.pl_tree_view` (QTreeView), `self.tb_table_view` (QTableView), `self.gl_table_view` (QTableView).
    *   A `gl_widget_container` (QWidget with QVBoxLayout) is created to hold the GL table and its summary labels.
    *   Respective models are instantiated: `QStandardItemModel` for tree views, and the new custom table models for table views.
    *   Views are added as pages to the `fs_display_stack`.
    *   GL Account ComboBox (`fs_gl_account_combo`) now has a `QCompleter` for better searching.
*   **`_on_fs_report_type_changed()`**:
    *   Logic to switch `fs_display_stack.setCurrentWidget()` based on selected report type.
    *   Clears the model of the *newly selected view* before new data is generated to avoid showing stale data.
*   **`_populate_hierarchical_model()` (New Helper Method)**:
    *   Takes a `QStandardItemModel`, report data, section keys, and formatting flags.
    *   Clears the model and sets horizontal headers.
    *   Iterates through sections and accounts, creating `QStandardItem`s and appending them hierarchically.
    *   Applies bold font to section titles and totals.
    *   Handles grand totals for P&L (Net Profit) and BS (Total L&E, balance warning).
*   **`_display_financial_report()`**:
    *   This method is now a dispatcher based on `report_data.get('title')`.
    *   For "Balance Sheet" and "Profit & Loss Statement", it calls `_populate_hierarchical_model` with the appropriate `QStandardItemModel` and section keys. It then expands the tree and resizes columns.
    *   For "Trial Balance", it calls `self.tb_model.update_data(report_data)`.
    *   For "General Ledger", it calls `self.gl_model.update_data(report_data)` and then updates the separate summary `QLabel`s (`gl_summary_label_account`, etc.) using `self.gl_model.get_report_summary()`.
*   **GL Display**: The General Ledger view now includes labels for Account Name, Period, Opening Balance, and Closing Balance outside the main transaction table, populated from `gl_model.get_report_summary()`.
*   **Decimal Formatting**: `_format_decimal_for_display` now has `show_blank_for_zero` parameter, used by GL and TB models to make tables cleaner.
*   **Error Handling & Logging**: Maintained from previous versions.
*   **QCompleter**: Added for `fs_gl_account_combo` to improve usability when selecting accounts.
*   **Layout for GL**: The GL Table is now part of a `gl_widget_container` so that summary labels can be placed above/below it.

This is a major refactoring of the report display. Thorough testing will be needed. The existing export functionality should still work as it relies on the `_current_financial_report_data` dictionary, which remains unchanged in its structure from the generator.

This completes the planned UI enhancements for displaying financial reports using native Qt views.
