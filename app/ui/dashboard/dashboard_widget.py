# app/ui/dashboard/dashboard_widget.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QGroupBox, QPushButton, QMessageBox,
    QScrollArea, QFrame, QFormLayout, QDateEdit
)
from PySide6.QtCore import Qt, Slot, QTimer, QMetaObject, Q_ARG, QMargins, QDate
from PySide6.QtGui import QFont, QIcon, QPainter, QColor
from PySide6.QtCharts import QChart, QChartView, QBarSet, QBarSeries, QBarCategoryAxis, QValueAxis

from typing import Optional, TYPE_CHECKING, List, Dict 
from decimal import Decimal, InvalidOperation 
import json 
from datetime import date as python_date, datetime, timedelta

from app.utils.pydantic_models import DashboardKPIData
from app.main import schedule_task_from_qt

if TYPE_CHECKING:
    from app.core.application_core import ApplicationCore 

class DashboardWidget(QWidget):
    def __init__(self, app_core: "ApplicationCore", parent: Optional[QWidget] = None): 
        super().__init__(parent)
        self.app_core = app_core
        self._load_request_count = 0 
        
        self.icon_path_prefix = "resources/icons/" 
        try:
            import app.resources_rc 
            self.icon_path_prefix = ":/icons/"
        except ImportError:
            pass
            
        self._group_colors = [QColor("#4F81BD"), QColor("#C0504D"), QColor("#9BBB59")]

        self._init_ui()
        self.app_core.logger.info("DashboardWidget: Scheduling initial KPI load.")
        QTimer.singleShot(0, self._request_kpi_load)

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        top_controls_layout = QHBoxLayout()
        top_controls_layout.addWidget(QLabel("<b>Dashboard As Of Date:</b>"))
        self.as_of_date_edit = QDateEdit(QDate.currentDate())
        self.as_of_date_edit.setCalendarPopup(True)
        self.as_of_date_edit.setDisplayFormat("dd/MM/yyyy")
        top_controls_layout.addWidget(self.as_of_date_edit)
        top_controls_layout.addStretch()
        self.refresh_button = QPushButton(QIcon(self.icon_path_prefix + "refresh.svg"), "Refresh KPIs")
        self.refresh_button.clicked.connect(self._request_kpi_load)
        top_controls_layout.addWidget(self.refresh_button)
        self.main_layout.addLayout(top_controls_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.main_layout.addWidget(scroll_area)

        container_widget = QWidget()
        scroll_area.setWidget(container_widget)
        
        container_layout = QVBoxLayout(container_widget)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        kpi_group = QGroupBox("Key Performance Indicators")
        container_layout.addWidget(kpi_group)
        
        self.kpi_layout = QGridLayout(kpi_group) 
        self.kpi_layout.setSpacing(10)
        self.kpi_layout.setColumnStretch(1, 1) 
        self.kpi_layout.setColumnStretch(3, 1) 
        self.kpi_layout.setColumnMinimumWidth(0, 220) 
        self.kpi_layout.setColumnMinimumWidth(2, 220) 

        def add_kpi_row(layout: QGridLayout, row: int, col_offset: int, title: str) -> QLabel:
            title_label = QLabel(title)
            title_label.setFont(QFont(self.font().family(), -1, QFont.Weight.Bold))
            value_label = QLabel("Loading...")
            value_label.setFont(QFont(self.font().family(), 11)) 
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(title_label, row, col_offset)
            layout.addWidget(value_label, row, col_offset + 1)
            return value_label

        current_row = 0
        self.period_label = QLabel("Period: Loading...")
        self.period_label.setStyleSheet("font-style: italic; color: grey;")
        self.kpi_layout.addWidget(self.period_label, current_row, 0, 1, 2, Qt.AlignmentFlag.AlignCenter) 

        self.base_currency_label = QLabel("Currency: Loading...")
        self.base_currency_label.setStyleSheet("font-style: italic; color: grey;")
        self.kpi_layout.addWidget(self.base_currency_label, current_row, 2, 1, 2, Qt.AlignmentFlag.AlignCenter) 
        current_row += 1
        
        self.revenue_value_label = add_kpi_row(self.kpi_layout, current_row, 0, "Total Revenue (YTD):")
        self.cash_balance_value_label = add_kpi_row(self.kpi_layout, current_row, 2, "Current Cash Balance:")
        current_row += 1
        self.expenses_value_label = add_kpi_row(self.kpi_layout, current_row, 0, "Total Expenses (YTD):")
        self.current_ratio_label = add_kpi_row(self.kpi_layout, current_row, 2, "Current Ratio:") 
        current_row += 1
        self.net_profit_value_label = add_kpi_row(self.kpi_layout, current_row, 0, "Net Profit / (Loss) (YTD):")
        self.quick_ratio_label = add_kpi_row(self.kpi_layout, current_row, 2, "Quick Ratio (Acid Test):")
        current_row += 1
        
        self.debt_to_equity_label = add_kpi_row(self.kpi_layout, current_row, 2, "Debt-to-Equity Ratio:")
        current_row += 1

        self.kpi_layout.addWidget(QLabel("---"), current_row, 0, 1, 4) 
        current_row += 1
        self.ar_value_label = add_kpi_row(self.kpi_layout, current_row, 0, "Total Outstanding AR:")
        self.ap_value_label = add_kpi_row(self.kpi_layout, current_row, 2, "Total Outstanding AP:")
        current_row += 1
        self.ar_overdue_value_label = add_kpi_row(self.kpi_layout, current_row, 0, "Total AR Overdue:")
        self.ap_overdue_value_label = add_kpi_row(self.kpi_layout, current_row, 2, "Total AP Overdue:")
        current_row += 1
        
        self.ar_aging_chart_view = self._create_aging_chart_view("AR Aging Summary")
        self.kpi_layout.addWidget(self.ar_aging_chart_view, current_row, 0, 1, 2) 

        self.ap_aging_chart_view = self._create_aging_chart_view("AP Aging Summary")
        self.kpi_layout.addWidget(self.ap_aging_chart_view, current_row, 2, 1, 2) 
        
        container_layout.addStretch() 

    def _create_aging_chart_view(self, title: str) -> QChartView:
        chart = QChart()
        chart.setTitle(title)
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        chart.legend().setVisible(False)
        chart.setMargins(QMargins(0,0,0,0))
        
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        chart_view.setMinimumHeight(250)
        return chart_view

    def _format_decimal_for_display(self, value: Optional[Decimal], currency_symbol: str = "") -> str:
        if value is None: return "N/A"
        prefix = f"{currency_symbol} " if currency_symbol else ""
        try:
            if not isinstance(value, Decimal) : value = Decimal(str(value))
            if not value.is_finite(): return "N/A (Infinite)" 
            return f"{prefix}{value:,.2f}"
        except (TypeError, InvalidOperation): return f"{prefix}Error"

    def _format_ratio_for_display(self, value: Optional[Decimal]) -> str:
        if value is None: return "N/A"
        try:
            if not isinstance(value, Decimal) : value = Decimal(str(value))
            if not value.is_finite(): return "N/A (Infinite)" 
            return f"{value:.2f} : 1"
        except (TypeError, InvalidOperation): return "Error"

    @Slot()
    def _request_kpi_load(self):
        self._load_request_count += 1
        self.app_core.logger.info(f"DashboardWidget: _request_kpi_load called (Count: {self._load_request_count}). Setting labels to 'Loading...'.")
        
        self.refresh_button.setEnabled(False)
        labels_to_reset = [
            self.revenue_value_label, self.expenses_value_label, self.net_profit_value_label,
            self.cash_balance_value_label, self.ar_value_label, self.ap_value_label,
            self.ar_overdue_value_label, self.ap_overdue_value_label,
            self.current_ratio_label, self.quick_ratio_label, self.debt_to_equity_label
        ]
        for label in labels_to_reset:
            if hasattr(self, 'app_core') and self.app_core and hasattr(self.app_core, 'logger'): 
                 self.app_core.logger.debug(f"DashboardWidget: Resetting label to 'Loading...'")
            label.setText("Loading...")
        
        self.ar_aging_chart_view.chart().removeAllSeries()
        self.ap_aging_chart_view.chart().removeAllSeries()

        self.period_label.setText("Period: Loading...")
        self.base_currency_label.setText("Currency: Loading...")

        as_of_date = self.as_of_date_edit.date().toPython()
        future = schedule_task_from_qt(self._fetch_kpis_data(as_of_date))
        if future:
            future.add_done_callback(
                lambda res: QMetaObject.invokeMethod(self.refresh_button, "setEnabled", Qt.ConnectionType.QueuedConnection, Q_ARG(bool, True))
            )
        else:
            self.app_core.logger.error("DashboardWidget: Failed to schedule _fetch_kpis_data task.")
            self.refresh_button.setEnabled(True) 

    async def _fetch_kpis_data(self, as_of_date: python_date):
        self.app_core.logger.info("DashboardWidget: _fetch_kpis_data started.")
        kpi_data_result: Optional[DashboardKPIData] = None
        json_payload: Optional[str] = None
        try:
            if not self.app_core.dashboard_manager:
                self.app_core.logger.error("DashboardWidget: Dashboard Manager not available in _fetch_kpis_data.")
            else:
                kpi_data_result = await self.app_core.dashboard_manager.get_dashboard_kpis(as_of_date=as_of_date)
                if kpi_data_result:
                    self.app_core.logger.info(f"DashboardWidget: Fetched KPI data: Period='{kpi_data_result.kpi_period_description}', Revenue='{kpi_data_result.total_revenue_ytd}'")
                    json_payload = kpi_data_result.model_dump_json()
                else:
                    self.app_core.logger.warning("DashboardWidget: DashboardManager.get_dashboard_kpis returned None.")
        except Exception as e:
            self.app_core.logger.error(f"DashboardWidget: Exception in _fetch_kpis_data during manager call: {e}", exc_info=True)
        
        self.app_core.logger.info(f"DashboardWidget: Queuing _update_kpi_display_slot with payload: {'JSON string' if json_payload else 'None'}")
        QMetaObject.invokeMethod(self, "_update_kpi_display_slot", Qt.ConnectionType.QueuedConnection, Q_ARG(str, json_payload if json_payload is not None else ""))

    @Slot(str)
    def _update_kpi_display_slot(self, kpi_data_json_str: str):
        self.app_core.logger.info(f"DashboardWidget: _update_kpi_display_slot called. Received JSON string length: {len(kpi_data_json_str)}")
        self.refresh_button.setEnabled(True)
        
        kpi_data_dto: Optional[DashboardKPIData] = None
        if kpi_data_json_str:
            try:
                kpi_data_dto = DashboardKPIData.model_validate_json(kpi_data_json_str)
                self.app_core.logger.info(f"DashboardWidget: Successfully deserialized KPI JSON to DTO.")
            except Exception as e:
                self.app_core.logger.error(f"DashboardWidget: Error deserializing/validating KPI JSON: '{kpi_data_json_str[:100]}...' - Error: {e}", exc_info=True)
        
        if kpi_data_dto:
            self.app_core.logger.info(f"DashboardWidget: Updating UI with KPI Data: Period='{kpi_data_dto.kpi_period_description}'")
            self.period_label.setText(f"Period: {kpi_data_dto.kpi_period_description}")
            self.base_currency_label.setText(f"Currency: {kpi_data_dto.base_currency}")
            bc_symbol = kpi_data_dto.base_currency 
            
            self.revenue_value_label.setText(self._format_decimal_for_display(kpi_data_dto.total_revenue_ytd, bc_symbol))
            self.expenses_value_label.setText(self._format_decimal_for_display(kpi_data_dto.total_expenses_ytd, bc_symbol))
            self.net_profit_value_label.setText(self._format_decimal_for_display(kpi_data_dto.net_profit_ytd, bc_symbol))
            self.cash_balance_value_label.setText(self._format_decimal_for_display(kpi_data_dto.current_cash_balance, bc_symbol))
            self.ar_value_label.setText(self._format_decimal_for_display(kpi_data_dto.total_outstanding_ar, bc_symbol))
            self.ap_value_label.setText(self._format_decimal_for_display(kpi_data_dto.total_outstanding_ap, bc_symbol))
            self.ar_overdue_value_label.setText(self._format_decimal_for_display(kpi_data_dto.total_ar_overdue, bc_symbol)) 
            self.ap_overdue_value_label.setText(self._format_decimal_for_display(kpi_data_dto.total_ap_overdue, bc_symbol)) 

            self._update_aging_chart(self.ar_aging_chart_view, kpi_data_dto, "ar")
            self.ap_aging_chart_view.chart().setTitleFont(QFont(self.font().family(), -1, QFont.Weight.Bold))
            self._update_aging_chart(self.ap_aging_chart_view, kpi_data_dto, "ap")
            
            self.current_ratio_label.setText(self._format_ratio_for_display(kpi_data_dto.current_ratio))
            self.quick_ratio_label.setText(self._format_ratio_for_display(kpi_data_dto.quick_ratio))
            self.debt_to_equity_label.setText(self._format_ratio_for_display(kpi_data_dto.debt_to_equity_ratio))

            self.app_core.logger.info("DashboardWidget: UI labels and charts updated with KPI data.")
        else:
            self.app_core.logger.warning("DashboardWidget: _update_kpi_display_slot called with no valid DTO. Setting error text.")
            error_text = "N/A - Data unavailable"
            for label in [self.revenue_value_label, self.expenses_value_label, self.net_profit_value_label,
                          self.cash_balance_value_label, self.ar_value_label, self.ap_value_label,
                          self.ar_overdue_value_label, self.ap_overdue_value_label,
                          self.current_ratio_label, self.quick_ratio_label, self.debt_to_equity_label]:
                label.setText(error_text)
            self.ar_aging_chart_view.chart().removeAllSeries()
            self.ap_aging_chart_view.chart().removeAllSeries()
            self.period_label.setText("Period: N/A")
            self.base_currency_label.setText("Currency: N/A")
            if kpi_data_json_str: 
                 QMessageBox.warning(self, "Dashboard Data Error", "Could not process Key Performance Indicators data.")

    def _update_aging_chart(self, chart_view: QChartView, kpi_data: DashboardKPIData, data_prefix: str):
        chart = chart_view.chart()
        chart.removeAllSeries()
        for axis in chart.axes(): chart.removeAxis(axis)

        bar_set = QBarSet("Amount")
        bar_set.setColor(QColor("#4F81BD"))
        
        aging_data = [
            kpi_data.ar_aging_current if data_prefix == "ar" else kpi_data.ap_aging_current,
            kpi_data.ar_aging_1_30 if data_prefix == "ar" else kpi_data.ap_aging_1_30,
            kpi_data.ar_aging_31_60 if data_prefix == "ar" else kpi_data.ap_aging_31_60,
            kpi_data.ar_aging_61_90 if data_prefix == "ar" else kpi_data.ap_aging_61_90,
            kpi_data.ar_aging_91_plus if data_prefix == "ar" else kpi_data.ap_aging_91_plus
        ]
        
        max_val = 0
        for val in aging_data:
            float_val = float(val)
            bar_set.append(float_val)
            if float_val > max_val: max_val = float_val

        series = QBarSeries()
        series.append(bar_set)
        series.setLabelsVisible(True)
        series.setLabelsFormat("@value")
        chart.addSeries(series)

        categories = ["Current", "1-30", "31-60", "61-90", "91+"]
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setLabelFormat("%'i")
        axis_y.setRange(0, max_val * 1.15 if max_val > 0 else 100)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)
