"""
PySide6 desktop frontend for the Budget App.
"""
import logging
import sys
from collections import defaultdict
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use('Agg')  # Render charts off-screen; they're shown as images
import matplotlib.colors as mcolors  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from PySide6.QtCore import QDate, QEasingCurve, QPropertyAnimation, Qt, QTimer, Signal  # noqa: E402
from PySide6.QtGui import QColor, QPixmap  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication, QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QGraphicsOpacityEffect, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QProgressBar,
    QProgressDialog, QPushButton, QScrollArea, QSizePolicy, QSplitter, QTableWidget,
    QTableWidgetItem, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from api_client import BudgetAppClient  # noqa: E402

logger = logging.getLogger("budgetapp.ui")


# ============ COLOR PALETTE ============
COLOR_PALETTE = {
    # Purple gradient theme
    'primary': '#2626fc',        # Bright blue-purple
    'primary_dark': '#010182',   # Deep navy-purple
    'primary_light': '#6464fb',  # Medium purple
    'success': '#10b981',        # Emerald green
    'danger': '#ef4444',         # Red
    'warning': '#f59e0b',        # Amber
    'info': '#3b82f6',           # Blue
    'background': '#f8f9fe',     # Very light purple-gray
    'background_dark': '#e8eaf6', # Light purple
    'surface': '#ffffff',        # Pure white
    'surface_alt': '#fafbff',    # Off-white with purple tint
    'border': '#d1d5e8',         # Soft purple-gray
    'text': '#1e1b4b',           # Deep purple-navy text
    'text_light': '#64748b',     # Medium gray
    'shadow': '#717689',         # Gray from palette
    
    # Extended palette
    'accent_purple': '#8b5cf6',  # Purple
    'accent_violet': '#a78bfa',  # Light violet
    'accent_indigo': '#6366f1',  # Indigo
    'accent_gray': '#a4a3ce',    # Light purple-gray from image
    'hover': '#e0e7ff',          # Light indigo hover
    'gradient_start': '#010182', # Gradient start
    'gradient_end': '#6464fb',   # Gradient end
    
    # Chart colors - purple/blue gradient series
    'chart_colors': [
        '#2626fc',  # Bright blue-purple
        '#6464fb',  # Medium purple
        '#8b5cf6',  # Purple
        '#a78bfa',  # Light violet
        '#6366f1',  # Indigo
        '#3b82f6',  # Blue
        '#10b981',  # Emerald
        '#f59e0b',  # Amber
        '#ef4444',  # Red
        '#a4a3ce',  # Purple-gray
    ]
}


# ============ ANIMATED WIDGETS ============

class AnimatedButton(QPushButton):
    """Button with smooth hover animations."""
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.default_color = QColor(COLOR_PALETTE['primary'])
        self.hover_color = QColor(COLOR_PALETTE['primary_dark'])
        self.current_color = self.default_color
        
        # Create opacity effect for smooth transitions
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(1.0)
        
        # Animation for color transitions (simulate with styleSheet)
        self.animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.animation.setDuration(150)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        
    def enterEvent(self, event):
        """Animate on hover."""
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.85)
        self.animation.start()
        self.setStyleSheet(f"background-color: {self.hover_color.name()};")
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        """Animate on hover leave."""
        self.animation.setStartValue(0.85)
        self.animation.setEndValue(1.0)
        self.animation.start()
        self.setStyleSheet(f"background-color: {self.default_color.name()};")
        super().leaveEvent(event)


# ============ CUSTOM WIDGETS ============

class CategoryTreeWidget(QTreeWidget):
    """Custom tree widget that properly handles category drag-and-drop."""
    
    category_moved = Signal(str, object)  # (category_id, new_parent_id)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def dropEvent(self, event):
        """Override dropEvent to capture category moves."""
        # Get the item being dragged
        dragged_items = self.selectedItems()
        if not dragged_items:
            return
            
        dragged_item = dragged_items[0]
        dragged_category_id = dragged_item.data(0, Qt.UserRole)
        
        # Let Qt handle the drop
        super().dropEvent(event)
        
        # After drop, find the new parent
        # The dragged item's parent has changed
        new_parent_item = dragged_item.parent()
        new_parent_id = new_parent_item.data(0, Qt.UserRole) if new_parent_item else None
        
        logger.debug(f"Drop detected: Category {dragged_category_id} -> Parent {new_parent_id}")
        
        # Emit signal for parent window to handle API update
        self.category_moved.emit(dragged_category_id, new_parent_id)


# ============ DIALOGS ============

class CreateTransactionDialog(QDialog):
    """Dialog to create a new transaction - AI-powered simplicity with optional manual fields."""

    def __init__(self, parent=None, categories: List[str] = None):
        super().__init__(parent)
        self.setWindowTitle("Quick Add Transaction")
        self.setModal(True)
        self.setGeometry(100, 100, 450, 450)
        
        self.categories = categories or []
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout()
        
        # Simple mode instructions
        info = QLabel("💡 Required: description & amount. AI fills the rest. Or specify manually below!")
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 10px;")
        layout.addRow(info)

        # REQUIRED FIELDS
        required_label = QLabel("<b>Required:</b>")
        layout.addRow(required_label)
        
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("e.g., 'chow', 'petrol station', 'groceries'")
        layout.addRow("Description:", self.desc_input)

        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("e.g., '1500', '45.50', '23.99'")
        layout.addRow("Amount:", self.amount_input)

        # OPTIONAL FIELDS
        optional_label = QLabel("<b>Optional:</b> (leave blank for AI auto-fill)")
        optional_label.setStyleSheet("margin-top: 15px;")
        layout.addRow(optional_label)
        
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setSpecialValueText("(Auto - today)")
        layout.addRow("Date:", self.date_edit)
        
        self.category_combo = QComboBox()
        self.category_combo.addItems(["(Auto - AI picks)"] + self.categories)
        layout.addRow("Category:", self.category_combo)
        
        self.merchant_input = QLineEdit()
        self.merchant_input.setPlaceholderText("(Auto-detected from description)")
        layout.addRow("Merchant:", self.merchant_input)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(["(Auto)", "expense", "income"])
        layout.addRow("Type:", self.type_combo)
        
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("Comma-separated tags (optional)")
        layout.addRow("Tags:", self.tags_input)
        
        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("Additional notes (optional)")
        layout.addRow("Notes:", self.notes_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.setLayout(layout)

    def get_data(self) -> Dict[str, Any]:
        """Get form data - required + optional fields."""
        data = {
            "description": self.desc_input.text().strip(),
            "amount": self.amount_input.text().strip()
        }
        
        # Add optional fields if specified
        if self.date_edit.date() != QDate.currentDate():
            data["date"] = self.date_edit.date().toString(Qt.ISODate)
            
        category = self.category_combo.currentText()
        if category and not category.startswith("(Auto"):
            data["category_path"] = category
            
        merchant = self.merchant_input.text().strip()
        if merchant:
            data["merchant"] = merchant
            
        trans_type = self.type_combo.currentText()
        if trans_type and not trans_type.startswith("(Auto"):
            data["transaction_type"] = trans_type
            
        tags = self.tags_input.text().strip()
        if tags:
            data["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
            
        notes = self.notes_input.text().strip()
        if notes:
            data["notes"] = notes
            
        return data


class EditTransactionDialog(QDialog):
    """Dialog to edit an existing transaction."""

    def __init__(self, parent=None, transaction: Dict = None, categories: List[str] = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Transaction")
        self.setModal(True)
        self.setGeometry(100, 100, 500, 400)
        
        self.transaction = transaction or {}
        self.categories = categories or []
        self.init_ui()
        self.populate_fields()

    def init_ui(self):
        layout = QFormLayout()

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        layout.addRow("Date:", self.date_edit)

        self.desc_input = QLineEdit()
        layout.addRow("Description:", self.desc_input)

        self.amount_input = QLineEdit()
        layout.addRow("Amount:", self.amount_input)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["expense", "income"])
        layout.addRow("Type:", self.type_combo)

        self.category_combo = QComboBox()
        self.category_combo.addItems(["(Uncategorized)"] + self.categories)
        layout.addRow("Category:", self.category_combo)

        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("Comma-separated tags")
        layout.addRow("Tags:", self.tags_input)

        self.notes_input = QLineEdit()
        layout.addRow("Notes:", self.notes_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.setLayout(layout)

    def populate_fields(self):
        """Populate fields with transaction data."""
        if not self.transaction:
            return
        
        # Date
        date_str = self.transaction.get("date", "")[:10]
        if date_str:
            date = QDate.fromString(date_str, "yyyy-MM-dd")
            self.date_edit.setDate(date)
        
        # Description
        self.desc_input.setText(self.transaction.get("description", ""))
        
        # Amount
        self.amount_input.setText(str(self.transaction.get("amount", 0)))
        
        # Type
        trans_type = self.transaction.get("transaction_type", "expense")
        self.type_combo.setCurrentText(trans_type)
        
        # Category
        category = self.transaction.get("category_path", "")
        if category:
            # Find and select the category
            index = self.category_combo.findText(category)
            if index >= 0:
                self.category_combo.setCurrentIndex(index)
            else:
                # Category not in list, add it and select it
                self.category_combo.addItem(category)
                self.category_combo.setCurrentText(category)
        else:
            # No category, select (Uncategorized)
            self.category_combo.setCurrentIndex(0)
        
        # Tags
        tags = self.transaction.get("tags", [])
        self.tags_input.setText(", ".join(tags))
        
        # Notes
        self.notes_input.setText(self.transaction.get("notes", ""))

    def get_data(self) -> Dict[str, Any]:
        """Get updated form data."""
        tags = [t.strip() for t in self.tags_input.text().split(",") if t.strip()]
        category = self.category_combo.currentText()
        
        # Get the original time component from transaction, or use midnight
        original_date = self.transaction.get("date", "")
        if "T" in original_date:
            time_part = original_date.split("T")[1]
        else:
            time_part = "00:00:00"
        
        return {
            "date": self.date_edit.date().toString(Qt.ISODate) + "T" + time_part,
            "description": self.desc_input.text().strip(),
            "amount": float(self.amount_input.text() or "0"),
            "transaction_type": self.type_combo.currentText(),
            "category_path": None if category == "(Uncategorized)" else category,
            "tags": tags,
            "notes": self.notes_input.text().strip() or None
        }


class CreateBudgetDialog(QDialog):
    """Dialog to create a budget."""

    def __init__(self, parent=None, categories: List[str] = None):
        super().__init__(parent)
        self.setWindowTitle("New Budget")
        self.setModal(True)
        self.setGeometry(100, 100, 500, 350)
        
        self.categories = categories or []
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout()

        self.category_combo = QComboBox()
        self.category_combo.addItems(["(Any)"] + self.categories)
        layout.addRow("Category:", self.category_combo)

        self.amount_input = QLineEdit()
        layout.addRow("Amount:", self.amount_input)

        self.period_combo = QComboBox()
        self.period_combo.addItems(["monthly", "quarterly", "yearly"])
        layout.addRow("Period:", self.period_combo)

        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate())
        layout.addRow("Start Date:", self.start_date)

        self.notes_input = QLineEdit()
        layout.addRow("Notes:", self.notes_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.setLayout(layout)
    
    def validate_and_accept(self):
        """Validate form before accepting."""
        try:
            amount = float(self.amount_input.text() or "0")
            if amount <= 0:
                QMessageBox.warning(self, "Invalid Amount", "Please enter a budget amount greater than 0")
                return
        except ValueError:
            QMessageBox.warning(self, "Invalid Amount", "Please enter a valid number for the budget amount")
            return
        
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        """Get form data."""
        return {
            "category_path": self.category_combo.currentText() if self.category_combo.currentText() != "(Any)" else None,
            "amount": float(self.amount_input.text() or "0"),
            "period": self.period_combo.currentText(),
            "start_date": self.start_date.date().toString(Qt.ISODate) + "T00:00:00",
            "notes": self.notes_input.text() or None
        }


class EditBudgetDialog(QDialog):
    """Dialog to edit an existing budget."""

    def __init__(self, parent=None, categories: List[str] = None, budget: Dict[str, Any] = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Budget")
        self.setModal(True)
        self.setGeometry(100, 100, 500, 350)
        
        self.categories = categories or []
        self.budget = budget or {}
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout()

        self.category_combo = QComboBox()
        self.category_combo.addItems(["(Any)"] + self.categories)
        # Set current category
        current_cat = self.budget.get("category_path")
        if current_cat:
            if self.category_combo.findText(current_cat) < 0:
                self.category_combo.addItem(current_cat)
            self.category_combo.setCurrentIndex(self.category_combo.findText(current_cat))
        layout.addRow("Category:", self.category_combo)

        self.amount_input = QLineEdit()
        self.amount_input.setText(str(self.budget.get("amount", "")))
        layout.addRow("Amount:", self.amount_input)

        self.period_combo = QComboBox()
        self.period_combo.addItems(["monthly", "quarterly", "yearly"])
        current_period = self.budget.get("period", "monthly")
        period_index = self.period_combo.findText(current_period)
        if period_index >= 0:
            self.period_combo.setCurrentIndex(period_index)
        layout.addRow("Period:", self.period_combo)

        self.start_date = QDateEdit()
        # Parse start date from budget
        start_date_str = self.budget.get("start_date", "")
        if start_date_str:
            try:
                dt = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
                self.start_date.setDate(QDate(dt.year, dt.month, dt.day))
            except:
                self.start_date.setDate(QDate.currentDate())
        else:
            self.start_date.setDate(QDate.currentDate())
        layout.addRow("Start Date:", self.start_date)

        self.notes_input = QLineEdit()
        self.notes_input.setText(self.budget.get("notes", "") or "")
        layout.addRow("Notes:", self.notes_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.setLayout(layout)
    
    def validate_and_accept(self):
        """Validate inputs before accepting."""
        try:
            amount = float(self.amount_input.text() or "0")
            if amount <= 0:
                QMessageBox.warning(self, "Invalid Amount", "Budget amount must be greater than 0")
                return
        except ValueError:
            QMessageBox.warning(self, "Invalid Amount", "Please enter a valid number for the budget amount")
            return
        
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        """Get form data."""
        return {
            "category_path": self.category_combo.currentText() if self.category_combo.currentText() != "(Any)" else None,
            "amount": float(self.amount_input.text() or "0"),
            "period": self.period_combo.currentText(),
            "start_date": self.start_date.date().toString(Qt.ISODate) + "T00:00:00",
            "notes": self.notes_input.text() or None
        }


class CreateCategoryDialog(QDialog):
    """Dialog to create a category."""

    def __init__(self, parent=None, parent_categories: List[str] = None):
        super().__init__(parent)
        self.setWindowTitle("New Category")
        self.setModal(True)
        self.setGeometry(100, 100, 400, 250)
        
        self.parent_categories = parent_categories or []
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout()

        self.name_input = QLineEdit()
        layout.addRow("Name:", self.name_input)

        self.parent_combo = QComboBox()
        self.parent_combo.addItems(["(Root)"] + self.parent_categories)
        layout.addRow("Parent:", self.parent_combo)

        self.icon_input = QLineEdit()
        self.icon_input.setPlaceholderText("e.g., 🍔")
        layout.addRow("Icon:", self.icon_input)

        self.color_input = QLineEdit()
        self.color_input.setPlaceholderText("e.g., #FF6B6B")
        layout.addRow("Color:", self.color_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.setLayout(layout)

    def get_data(self) -> Dict[str, Any]:
        """Get form data."""
        parent_text = self.parent_combo.currentText()
        
        # Need to convert parent category name to ID
        # For now, use None for root, otherwise pass the name and let backend handle it
        parent_id = None if parent_text == "(Root)" else parent_text
        
        return {
            "name": self.name_input.text(),
            "parent_id": parent_id,
            "icon": self.icon_input.text(),
            "color": self.color_input.text(),
        }


# ============ MAIN WINDOW ============

class BudgetAppMainWindow(QMainWindow):
    """Main window for the Budget App."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("💰 Budget App - Financial Management")
        self.setGeometry(100, 100, 1400, 900)
        
        # Modern styling with gradient background and animations
        self.setStyleSheet(f"""
            QMainWindow {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLOR_PALETTE['background']},
                    stop:1 {COLOR_PALETTE['background_dark']});
            }}
            QPushButton {{
                background-color: {COLOR_PALETTE['primary']};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {COLOR_PALETTE['primary_dark']};
            }}
            QPushButton:pressed {{
                background-color: {COLOR_PALETTE['primary_dark']};
                padding: 9px 15px 7px 17px;
            }}
            QTableWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLOR_PALETTE['surface']},
                    stop:1 {COLOR_PALETTE['surface_alt']});
                border: 1px solid {COLOR_PALETTE['border']};
                border-radius: 4px;
                gridline-color: {COLOR_PALETTE['border']};
            }}
            QTableWidget::item {{
                padding: 8px;
            }}
            QTableWidget::item:selected {{
                background-color: {COLOR_PALETTE['primary_light']};
                color: {COLOR_PALETTE['text']};
            }}
            QHeaderView::section {{
                background-color: {COLOR_PALETTE['primary']};
                color: white;
                padding: 10px;
                border: none;
                font-weight: bold;
            }}
            QTreeWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLOR_PALETTE['surface']},
                    stop:1 {COLOR_PALETTE['surface_alt']});
                border: 1px solid {COLOR_PALETTE['border']};
                border-radius: 4px;
            }}
            QTreeWidget::item {{
                padding: 6px;
            }}
            QTreeWidget::item:selected {{
                background-color: {COLOR_PALETTE['primary_light']};
                color: {COLOR_PALETTE['text']};
            }}
            QTabWidget::pane {{
                border: 1px solid {COLOR_PALETTE['border']};
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLOR_PALETTE['surface']},
                    stop:1 {COLOR_PALETTE['background']});
                border-radius: 4px;
            }}
            QTabBar::tab {{
                background-color: {COLOR_PALETTE['background']};
                color: {COLOR_PALETTE['text']};
                padding: 12px 24px;
                margin-right: 3px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 15px;
            }}
            QTabBar::tab:selected {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLOR_PALETTE['surface']},
                    stop:1 {COLOR_PALETTE['hover']});
                color: {COLOR_PALETTE['primary']};
                font-weight: bold;
                border-bottom: 3px solid {COLOR_PALETTE['primary']};
            }}
            QTabBar::tab:hover {{
                background-color: {COLOR_PALETTE['hover']};
            }}
            QLineEdit, QComboBox, QDateEdit, QSpinBox {{
                padding: 6px 10px;
                border: 1px solid {COLOR_PALETTE['border']};
                border-radius: 4px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLOR_PALETTE['surface']},
                    stop:1 {COLOR_PALETTE['surface_alt']});
                color: {COLOR_PALETTE['text']};
                font-size: 14px;
            }}
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{
                border: 2px solid {COLOR_PALETTE['primary']};
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLOR_PALETTE['surface_alt']},
                    stop:1 {COLOR_PALETTE['hover']});
            }}
            QComboBox::drop-down {{
                border: none;
                background: {COLOR_PALETTE['primary']};
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
                width: 25px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border: 5px solid transparent;
                border-top: 6px solid white;
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLOR_PALETTE['surface']},
                    stop:1 {COLOR_PALETTE['surface_alt']});
                border: 2px solid {COLOR_PALETTE['primary']};
                border-radius: 4px;
                selection-background-color: {COLOR_PALETTE['primary_light']};
                selection-color: {COLOR_PALETTE['text']};
                color: {COLOR_PALETTE['text']};
                padding: 4px;
            }}
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLOR_PALETTE['primary']},
                    stop:1 {COLOR_PALETTE['gradient_end']});
                color: white;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
                border: none;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLOR_PALETTE['gradient_end']},
                    stop:1 {COLOR_PALETTE['primary']});
            }}
            QPushButton:pressed {{
                background: {COLOR_PALETTE['primary_dark']};
                padding: 9px 16px 7px 16px;
            }}
            QLabel {{
                color: {COLOR_PALETTE['text']};
            }}
            QTableWidget {{
                border: 1px solid {COLOR_PALETTE['border']};
                border-radius: 5px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLOR_PALETTE['surface']},
                    stop:1 {COLOR_PALETTE['surface_alt']});
                gridline-color: {COLOR_PALETTE['shadow']};
                alternate-background-color: {COLOR_PALETTE['surface']};
            }}
            QTableWidget::item {{
                padding: 8px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLOR_PALETTE['surface']},
                    stop:1 {COLOR_PALETTE['surface_alt']});
                color: {COLOR_PALETTE['text']};
                border: none;
            }}
            QTableWidget::item:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLOR_PALETTE['hover']},
                    stop:1 {COLOR_PALETTE['surface']});
            }}
            QTableWidget::item:selected {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLOR_PALETTE['primary_light']},
                    stop:1 {COLOR_PALETTE['gradient_end']});
                color: white;
            }}
            QHeaderView::section {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLOR_PALETTE['gradient_start']},
                    stop:1 {COLOR_PALETTE['gradient_end']});
                padding: 8px;
                border: none;
                font-weight: bold;
                color: white;
            }}
            QGroupBox {{
                border: 1px solid {COLOR_PALETTE['border']};
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 18px;
                font-weight: bold;
                font-size: 13px;
                color: {COLOR_PALETTE['text']};
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLOR_PALETTE['surface']},
                    stop:1 {COLOR_PALETTE['surface_alt']});
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 8px;
                padding: 0 5px;
                top: -8px;
            }}
        """)

        self.client = BudgetAppClient()
        self.categories_list = []
        self.transactions = []
        self.budgets = []
        self.budget_statuses = []
        self.unknowns = []  # Store unknowns separately
        
        # Filter state
        self.active_date_from = None
        self.active_date_to = None
        self.active_category_filters = []  # List of selected category IDs

        self.init_ui()
        self.load_data()

    def init_ui(self):
        """Initialize UI components."""
        central = QWidget()
        layout = QHBoxLayout()

        # Left panel: Category tree
        self.category_tree = CategoryTreeWidget()
        self.category_tree.setHeaderLabel("Categories")
        self.category_tree.setDragDropMode(QTreeWidget.InternalMove)
        self.category_tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.category_tree.setDragEnabled(True)
        self.category_tree.setAcceptDrops(True)
        self.category_tree.setDropIndicatorShown(True)
        # Connect custom signal from CategoryTreeWidget
        self.category_tree.category_moved.connect(self.on_category_moved_signal)
        self.category_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.category_tree.customContextMenuRequested.connect(self.show_category_menu)

        # Right panel: Tabs
        tabs = QTabWidget()

        # Tab 0: Dashboard with Charts
        dashboard_widget = QWidget()
        dashboard_layout = QVBoxLayout()
        
        # Dashboard title with refresh button
        title_row = QHBoxLayout()
        dashboard_title = QLabel("<h2>📊 Financial Dashboard</h2>")
        title_row.addWidget(dashboard_title)
        title_row.addStretch()
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.update_dashboard)
        title_row.addWidget(refresh_btn)
        dashboard_layout.addLayout(title_row)
        
        # Summary Stats Row
        stats_row = QHBoxLayout()
        self.total_income_label = QLabel("<b>Total Income:</b> R0.00")
        self.total_expenses_label = QLabel("<b>Total Expenses:</b> R0.00")
        self.net_balance_label = QLabel("<b>Net Balance:</b> R0.00")
        self.avg_daily_label = QLabel("<b>Avg Daily Spend:</b> R0.00")
        
        for label in [self.total_income_label, self.total_expenses_label, self.net_balance_label, self.avg_daily_label]:
            label.setStyleSheet(f"padding: 10px; background: {COLOR_PALETTE['surface_alt']}; border-radius: 4px; font-size: 13px; border: 1px solid {COLOR_PALETTE['border']};")
        
        stats_row.addWidget(self.total_income_label)
        stats_row.addWidget(self.total_expenses_label)
        stats_row.addWidget(self.net_balance_label)
        stats_row.addWidget(self.avg_daily_label)
        dashboard_layout.addLayout(stats_row)
        
        # Charts container - 2 rows of 2 charts
        charts_row1 = QHBoxLayout()
        charts_row2 = QHBoxLayout()
        
        # Chart 1 Container: Spending by Category (Pie Chart)
        chart1_container = QVBoxLayout()
        
        self.category_chart_label = QLabel()
        self.category_chart_label.setMinimumSize(400, 300)
        self.category_chart_label.setScaledContents(False)
        self.category_chart_label.setAlignment(Qt.AlignCenter)
        self.category_chart_label.setStyleSheet(f"""
            border: 2px solid {COLOR_PALETTE['border']}; 
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {COLOR_PALETTE['surface']},
                stop:1 {COLOR_PALETTE['surface_alt']}); 
            border-radius: 8px; 
            padding: 10px;
        """)
        chart1_container.addWidget(self.category_chart_label)
        
        chart1_widget = QWidget()
        chart1_widget.setLayout(chart1_container)
        charts_row1.addWidget(chart1_widget, 1)  # Stretch factor 1
        
        # Chart 2: Spending Over Time (Line Chart)
        self.spending_time_chart = QLabel()
        self.spending_time_chart.setMinimumSize(400, 300)
        self.spending_time_chart.setScaledContents(False)
        self.spending_time_chart.setAlignment(Qt.AlignCenter)
        self.spending_time_chart.setStyleSheet(f"border: 1px solid {COLOR_PALETTE['border']}; background: {COLOR_PALETTE['surface_alt']}; border-radius: 4px; padding: 10px;")
        self.spending_time_chart.setMinimumSize(400, 300)
        self.spending_time_chart.setStyleSheet(f"border: 1px solid {COLOR_PALETTE['border']}; background: {COLOR_PALETTE['surface_alt']}; border-radius: 4px; padding: 10px;")
        charts_row1.addWidget(self.spending_time_chart, 1)  # Stretch factor 1
        
        dashboard_layout.addLayout(charts_row1)
        
        # Charts Row 2
        charts_row2 = QHBoxLayout()
        
        # Chart 3: Budget Progress (Bar Chart)
        self.budget_chart_label = QLabel()
        self.budget_chart_label.setMinimumSize(400, 300)
        self.budget_chart_label.setScaledContents(False)
        self.budget_chart_label.setAlignment(Qt.AlignCenter)
        self.budget_chart_label.setStyleSheet(f"border: 1px solid {COLOR_PALETTE['border']}; background: {COLOR_PALETTE['surface_alt']}; border-radius: 4px; padding: 10px;")
        charts_row2.addWidget(self.budget_chart_label, 1)
        
        # Chart 4: Top Spending Categories (Horizontal Bar)
        self.top_categories_chart = QLabel()
        self.top_categories_chart.setMinimumSize(400, 300)
        self.top_categories_chart.setScaledContents(False)
        self.top_categories_chart.setAlignment(Qt.AlignCenter)
        self.top_categories_chart.setStyleSheet(f"border: 1px solid {COLOR_PALETTE['border']}; background: {COLOR_PALETTE['surface_alt']}; border-radius: 4px; padding: 10px;")
        charts_row2.addWidget(self.top_categories_chart, 1)
        
        dashboard_layout.addLayout(charts_row2)
        
        # Charts Row 3 - Income
        charts_row3 = QHBoxLayout()
        
        # Chart 5: Income by Category (Pie Chart)
        income_chart_container = QVBoxLayout()
        income_header = QHBoxLayout()
        income_title = QLabel("💰 Income by Source")
        income_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        income_header.addWidget(income_title)
        income_header.addStretch()
        income_chart_container.addLayout(income_header)
        
        self.income_chart_label = QLabel()
        self.income_chart_label.setMinimumSize(500, 400)
        self.income_chart_label.setStyleSheet("border: 1px solid #ddd; background: " + COLOR_PALETTE['surface_alt'] + "; border-radius: 8px; padding: 10px;")
        income_chart_container.addWidget(self.income_chart_label)
        
        income_widget = QWidget()
        income_widget.setLayout(income_chart_container)
        charts_row3.addWidget(income_widget)
        charts_row3.addStretch()
        
        dashboard_layout.addLayout(charts_row3)
        dashboard_layout.addStretch()
        dashboard_widget.setLayout(dashboard_layout)
        dashboard_widget.setStyleSheet(f"""
            QWidget#dashboard_widget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLOR_PALETTE['background']},
                    stop:1 {COLOR_PALETTE['background_dark']});
            }}
        """)
        dashboard_widget.setObjectName("dashboard_widget")
        
        # Wrap dashboard in scroll area
        dashboard_scroll = QScrollArea()
        dashboard_scroll.setWidget(dashboard_widget)
        dashboard_scroll.setWidgetResizable(True)
        dashboard_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        dashboard_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        dashboard_scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLOR_PALETTE['background']},
                    stop:1 {COLOR_PALETTE['background_dark']});
            }}
        """)
        tabs.addTab(dashboard_scroll, "📊 Dashboard")

        # Tab 1: Transactions
        self.transactions_table = QTableWidget()
        self.transactions_table.setColumnCount(7)
        self.transactions_table.setHorizontalHeaderLabels([
            "Date", "Description", "Amount", "Category", "Tags", "Edit", "Delete"
        ])
        self.transactions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.transactions_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.transactions_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)
        self.transactions_table.horizontalHeader().resizeSection(5, 160)
        self.transactions_table.horizontalHeader().resizeSection(6, 160)
        self.transactions_table.verticalHeader().setDefaultSectionSize(35)
        self.transactions_table.setSortingEnabled(True)
        self.transactions_table.setAlternatingRowColors(True)
        self.transactions_table.setEditTriggers(QTableWidget.NoEditTriggers)
        tabs.addTab(self.transactions_table, "Transactions")

        # Tab 2: Budgets
        self.budgets_table = QTableWidget()
        self.budgets_table.setColumnCount(7)
        self.budgets_table.setHorizontalHeaderLabels([
            "Category", "Budget", "Spent", "Progress", "Status", "Edit", "Delete"
        ])
        self.budgets_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.budgets_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.budgets_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)
        self.budgets_table.horizontalHeader().resizeSection(5, 180)
        self.budgets_table.horizontalHeader().resizeSection(6, 180)
        self.budgets_table.verticalHeader().setDefaultSectionSize(40)
        self.budgets_table.setEditTriggers(QTableWidget.NoEditTriggers)
        tabs.addTab(self.budgets_table, "Budgets")

        # Tab 3: Unknowns
        self.unknowns_table = QTableWidget()
        self.unknowns_table.setColumnCount(4)
        self.unknowns_table.setHorizontalHeaderLabels([
            "Date", "Description", "Amount", "Actions"
        ])
        self.unknowns_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.unknowns_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.unknowns_table.horizontalHeader().resizeSection(3, 160)
        self.unknowns_table.verticalHeader().setDefaultSectionSize(35)
        self.unknowns_table.setSortingEnabled(True)
        self.unknowns_table.setAlternatingRowColors(True)
        self.unknowns_table.setEditTriggers(QTableWidget.NoEditTriggers)
        tabs.addTab(self.unknowns_table, "Unknowns")

        # Tab 4: Possible Duplicates
        self.duplicates_table = QTableWidget()
        self.duplicates_table.setColumnCount(6)
        self.duplicates_table.setHorizontalHeaderLabels([
            "Date", "Description", "Amount", "Match", "Keep", "Delete"
        ])
        self.duplicates_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.duplicates_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.duplicates_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.duplicates_table.horizontalHeader().resizeSection(4, 160)
        self.duplicates_table.horizontalHeader().resizeSection(5, 160)
        self.duplicates_table.verticalHeader().setDefaultSectionSize(35)
        self.duplicates_table.setSortingEnabled(True)
        self.duplicates_table.setAlternatingRowColors(True)
        self.duplicates_table.setEditTriggers(QTableWidget.NoEditTriggers)
        tabs.addTab(self.duplicates_table, "Possible Duplicates")

        # Tab 5: Merchants / Relationships
        self.merchants_table = QTableWidget()
        self.merchants_table.setColumnCount(4)
        self.merchants_table.setHorizontalHeaderLabels([
            "Merchant", "Preferred Category", "Confidence", "Delete"
        ])
        self.merchants_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.merchants_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.merchants_table.horizontalHeader().resizeSection(3, 180)
        self.merchants_table.verticalHeader().setDefaultSectionSize(40)
        self.merchants_table.setSortingEnabled(True)
        self.merchants_table.setAlternatingRowColors(True)
        self.merchants_table.setEditTriggers(QTableWidget.NoEditTriggers)
        tabs.addTab(self.merchants_table, "📚 Merchants")

        # Tab 6: Import
        import_layout = QVBoxLayout()
        import_widget = QWidget()
        
        import_buttons = QHBoxLayout()
        import_csv_btn = QPushButton("📄 Import Bank CSV")
        import_csv_btn.clicked.connect(self.import_csv)
        import_buttons.addWidget(import_csv_btn)
        
        import_buttons.addStretch()
        
        import_layout.addLayout(import_buttons)
        
        # Info text
        info_label = QLabel(
            "<b>Import Instructions:</b><br>"
            "<b>CSV Import:</b> Export bank statement as CSV and upload<br><br>"
            "<i>AI will auto-categorize imported transactions</i>"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 10px; background-color: #E3F2FD; border-radius: 4px;")
        import_layout.addWidget(info_label)
        
        # Status label for import feedback
        self.import_status = QLabel("")
        self.import_status.setWordWrap(True)
        import_layout.addWidget(self.import_status)
        
        import_layout.addStretch()
        import_widget.setLayout(import_layout)
        tabs.addTab(import_widget, "Import")

        # Toolbar - compact layout with height constraint
        toolbar_layout = QVBoxLayout()
        toolbar_layout.setSpacing(4)  # Minimal spacing between rows
        toolbar_layout.setContentsMargins(4, 4, 4, 4)  # Tight margins
        
        # Row 1: Action buttons
        toolbar_buttons = QHBoxLayout()

        new_trans_btn = QPushButton("New Transaction")
        new_trans_btn.clicked.connect(self.new_transaction)
        toolbar_buttons.addWidget(new_trans_btn)

        new_budget_btn = QPushButton("New Budget")
        new_budget_btn.clicked.connect(self.new_budget)
        toolbar_buttons.addWidget(new_budget_btn)

        new_category_btn = QPushButton("New Category")
        new_category_btn.clicked.connect(self.new_category)
        toolbar_buttons.addWidget(new_category_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_data)
        toolbar_buttons.addWidget(refresh_btn)
        toolbar_buttons.addStretch()  # Push buttons to left

        toolbar_layout.addLayout(toolbar_buttons)
        
        # Row 2: Filters
        filters_layout = QHBoxLayout()
        
        # Date range filter - compact horizontal layout
        date_group = QGroupBox("Date Range")
        date_group.setMaximumWidth(350)
        date_group.setMaximumHeight(65)  # Constrain height
        date_layout = QHBoxLayout()
        date_layout.setContentsMargins(4, 2, 4, 2)  # Minimal margins
        date_layout.setSpacing(4)  # Tight spacing
        
        from_label = QLabel("From:")
        from_label.setStyleSheet(f"font-size: 13px; color: {COLOR_PALETTE['text_light']};")
        date_layout.addWidget(from_label)
        
        self.date_from = QDateEdit()
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        self.date_from.setCalendarPopup(True)
        self.date_from.dateChanged.connect(self.apply_filters)
        self.date_from.setMaximumHeight(28)
        self.date_from.setStyleSheet("padding: 2px; font-size: 13px;")
        date_layout.addWidget(self.date_from)
        
        to_label = QLabel("To:")
        to_label.setStyleSheet(f"font-size: 13px; color: {COLOR_PALETTE['text_light']};")
        date_layout.addWidget(to_label)
        
        self.date_to = QDateEdit()
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.dateChanged.connect(self.apply_filters)
        self.date_to.setMaximumHeight(28)
        self.date_to.setStyleSheet("padding: 2px; font-size: 13px;")
        date_layout.addWidget(self.date_to)
        
        date_group.setLayout(date_layout)
        filters_layout.addWidget(date_group)
        
        # Category multi-select filter with checkboxes
        category_group = QGroupBox("Categories")
        category_group.setMaximumHeight(95)  # Better readability
        category_group.setMinimumWidth(180)  # Prevent text cutoff
        category_layout = QVBoxLayout()
        category_layout.setContentsMargins(4, 2, 4, 2)  # Minimal margins
        category_layout.setSpacing(2)
        
        # Container for checkbox grid
        
        # Scrollable area for checkboxes
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setMaximumHeight(65)  # Compact height with better readability
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {COLOR_PALETTE['border']};
                border-radius: 3px;
                background: {COLOR_PALETTE['surface_alt']};
            }}
            QScrollBar:vertical {{
                width: 6px;
                background: {COLOR_PALETTE['background']};
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLOR_PALETTE['primary_light']};
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {COLOR_PALETTE['primary']};
            }}
        """)
        
        self.category_checkboxes_container = QWidget()
        self.category_checkboxes_layout = QGridLayout()
        self.category_checkboxes_layout.setSpacing(2)
        self.category_checkboxes_layout.setContentsMargins(2, 2, 2, 2)
        self.category_checkboxes_container.setLayout(self.category_checkboxes_layout)
        self.category_checkboxes_container.setObjectName("category_checkboxes_container")
        self.category_checkboxes_container.setStyleSheet(f"""
            QWidget#category_checkboxes_container {{
                background: {COLOR_PALETTE['surface_alt']};
            }}
            QCheckBox {{
                padding: 2px;
                spacing: 2px;
                font-size: 12px;
                color: {COLOR_PALETTE['text']};
            }}
            QCheckBox::indicator {{
                width: 12px;
                height: 12px;
                border: 1px solid {COLOR_PALETTE['border']};
                border-radius: 2px;
            }}
            QCheckBox::indicator:checked {{
                background: {COLOR_PALETTE['primary']};
                border: 1px solid {COLOR_PALETTE['primary']};
            }}
            QCheckBox::indicator:hover {{
                border: 1px solid {COLOR_PALETTE['primary_light']};
            }}
        """)
        
        # Store checkboxes for later access
        self.category_checkboxes = {}
        
        scroll_area.setWidget(self.category_checkboxes_container)
        category_layout.addWidget(scroll_area)
        category_group.setLayout(category_layout)
        filters_layout.addWidget(category_group)
        
        # Clear filters button - using AnimatedButton for smooth animations
        clear_layout = QVBoxLayout()
        clear_layout.setSpacing(0)
        clear_layout.setContentsMargins(0, 0, 0, 0)
        clear_filters_btn = AnimatedButton("🔄 Clear")
        clear_filters_btn.setFixedWidth(85)
        clear_filters_btn.setMaximumHeight(35)
        clear_filters_btn.clicked.connect(self.clear_filters)
        clear_filters_btn.default_color = QColor(COLOR_PALETTE['danger'])
        clear_filters_btn.hover_color = QColor(COLOR_PALETTE['accent_purple'])
        clear_filters_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR_PALETTE['danger']};
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                border: none;
                font-size: 14px;
            }}
        """)
        clear_layout.addWidget(clear_filters_btn)
        filters_layout.addLayout(clear_layout)
        
        # Add filters to toolbar WITHOUT stretch
        toolbar_layout.addLayout(filters_layout)
        
        # Create toolbar container with max height
        toolbar_container = QWidget()
        toolbar_container.setLayout(toolbar_layout)
        toolbar_container.setMaximumHeight(160)  # Constrain total toolbar height
        toolbar_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        toolbar_container.setStyleSheet(f"""
            QWidget#toolbar_container {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLOR_PALETTE['surface']},
                    stop:1 {COLOR_PALETTE['surface_alt']});
            }}
        """)
        toolbar_container.setObjectName("toolbar_container")

        # Main layout with splitter for dynamic resizing
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Categories"))
        left_layout.addWidget(self.category_tree)

        left_widget = QWidget()
        left_widget.setLayout(left_layout)
        left_widget.setMinimumWidth(200)
        left_widget.setMaximumWidth(300)
        left_widget.setStyleSheet(f"""
            QWidget#left_widget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLOR_PALETTE['background']},
                    stop:1 {COLOR_PALETTE['background_dark']});
            }}
        """)
        left_widget.setObjectName("left_widget")

        right_layout = QVBoxLayout()
        right_layout.setSpacing(0)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(toolbar_container)  # Use container with height limit
        right_layout.addWidget(tabs)

        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        right_widget.setStyleSheet(f"""
            QWidget#right_widget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLOR_PALETTE['background']},
                    stop:1 {COLOR_PALETTE['background_dark']});
            }}
        """)
        right_widget.setObjectName("right_widget")
        
        # Use QSplitter for resizable panes
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 0)  # Left panel fixed-ish
        splitter.setStretchFactor(1, 1)  # Right panel stretches
        splitter.setSizes([250, 1150])  # Initial sizes

        main_container = QWidget()
        container_layout = QHBoxLayout()
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(splitter)
        main_container.setLayout(container_layout)
        main_container.setStyleSheet(f"""
            QWidget#main_container {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLOR_PALETTE['background']},
                    stop:1 {COLOR_PALETTE['background_dark']});
            }}
        """)
        main_container.setObjectName("main_container")

        central.setLayout(layout)
        self.setCentralWidget(main_container)
        
        # Add status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

    def load_data(self):
        """Load data from backend."""
        self.load_categories()
        self.load_transactions()
        self.load_budgets()
        self.load_unknowns()
        self.load_duplicates()
        self.load_merchants()
        self.update_dashboard()

    def load_categories(self):
        """Load and display categories."""
        try:
            data = self.client.get_categories()
            self.category_tree.clear()
            
            nodes = data.get("nodes", {})
            root_ids = data.get("root_ids", [])
            
            self.categories_list = []
            
            def add_node(parent_id, parent_widget=None, parent_path=""):
                if parent_id in nodes:
                    node = nodes[parent_id]
                    name = f"{node.get('icon', '')} {node.get('name', '')}".strip()
                    
                    item = QTreeWidgetItem()
                    item.setText(0, name)
                    item.setData(0, Qt.UserRole, parent_id)
                    
                    if parent_widget:
                        parent_widget.addChild(item)
                    else:
                        self.category_tree.addTopLevelItem(item)
                    
                    path = f"{parent_path}/{node.get('name', '')}" if parent_path else node.get('name', '')
                    self.categories_list.append({
                        'id': parent_id,
                        'name': node.get('name', ''),
                        'parent_id': node.get('parent_id'),
                        'path': path,
                        'icon': node.get('icon', '')
                    })
                    
                    for child_id in node.get("children", []):
                        add_node(child_id, item, path)
            
            for root_id in root_ids:
                add_node(root_id)
            
            self.category_tree.expandAll()
            
            # Update category filter dropdown
            self.update_category_filter_dropdown()
            
        except Exception as e:
            self.show_error(f"Failed to load categories: {e}")
    
    def update_category_filter_dropdown(self):
        """Update the category filter checkboxes with current categories."""
        try:
            
            # Save current selections
            selected_names = [name for name, cb in self.category_checkboxes.items() if cb.isChecked()]
            
            # Clear existing checkboxes
            for i in reversed(range(self.category_checkboxes_layout.count())):
                widget = self.category_checkboxes_layout.itemAt(i).widget()
                if widget:
                    widget.deleteLater()
            self.category_checkboxes.clear()
            
            # Add checkboxes in a grid (8 columns for maximum horizontal spread)
            cols = 8
            for idx, cat in enumerate(self.categories_list):
                cat_name = cat.get("name", "")
                cat_id = cat.get("id")
                
                checkbox = QCheckBox(cat_name)
                checkbox.setProperty("category_id", cat_id)
                checkbox.stateChanged.connect(self.apply_filters)
                
                # Restore selection if previously selected
                if cat_name in selected_names:
                    checkbox.setChecked(True)
                
                # Add to grid
                row = idx // cols
                col = idx % cols
                self.category_checkboxes_layout.addWidget(checkbox, row, col)
                
                # Store reference
                self.category_checkboxes[cat_name] = checkbox
                    
        except Exception as e:
            logger.exception(f"Failed to update category filter: {e}")
    
    def apply_filters(self):
        """Apply the current filter settings to all tabs."""
        # Save filter state
        if self.date_from.date().isValid():
            self.active_date_from = self.date_from.date().toString("yyyy-MM-dd")
        else:
            self.active_date_from = None
            
        if self.date_to.date().isValid():
            self.active_date_to = self.date_to.date().toString("yyyy-MM-dd")
        else:
            self.active_date_to = None
        
        # Get all selected categories from checkboxes
        self.active_category_filters = []
        for cat_name, checkbox in self.category_checkboxes.items():
            if checkbox.isChecked():
                category_id = checkbox.property("category_id")
                if category_id:
                    self.active_category_filters.append(category_id)
        
        # Reload all data with filters
        self.load_transactions()
        self.load_budgets()
        self.load_unknowns()
        self.load_duplicates()
        self.update_dashboard()
    
    def clear_filters(self):
        """Clear all active filters."""
        # Clear UI
        self.date_from.clear()
        self.date_to.clear()
        # Uncheck all category checkboxes
        for checkbox in self.category_checkboxes.values():
            checkbox.setChecked(False)
        
        # Clear state
        self.active_date_from = None
        self.active_date_to = None
        self.active_category_filters = []
        
        # Reload all data
        self.load_transactions()
        self.load_budgets()
        self.load_unknowns()
        self.load_duplicates()
        self.update_dashboard()
    
    def on_category_moved_signal(self, category_id: str, new_parent_id):
        """Persist a drag-and-drop move of a category in the tree."""
        try:
            self.client.update_category(category_id, parent_id=new_parent_id)
            self.show_info("Category moved successfully")
            QTimer.singleShot(100, self.load_categories)  # Small delay to let tree settle
        except Exception as e:
            self.show_error(f"Failed to move category: {e}")
            self.load_categories()  # Reload to revert
    
    def category_paths(self) -> List[str]:
        """Full paths of all categories, e.g. 'Food & Dining/Groceries'."""
        return [cat['path'] for cat in self.categories_list]
    
    def matches_category_filter(self, category_path: Optional[str]) -> bool:
        """True if a category path falls under one of the checked category filters."""
        if not category_path:
            return False
        selected = {cat['name'] for cat in self.categories_list if cat['id'] in self.active_category_filters}
        return any(f"/{name}/" in f"/{category_path}/" for name in selected)

    def load_transactions(self):
        """Load and display transactions."""
        try:
            logger.debug("Loading transactions from API...")
            data = self.client.list_transactions(limit=10000)
            all_transactions = data.get("transactions", [])
            logger.debug(f"Loaded {len(all_transactions)} transactions")
            
            # Apply filters
            filtered_transactions = []
            for trans in all_transactions:
                # Date filter
                trans_date = trans.get("date", "")
                if self.active_date_from and trans_date < self.active_date_from:
                    continue
                if self.active_date_to and trans_date > self.active_date_to:
                    continue
                
                # Category filter - check if transaction category is in selected categories
                if self.active_category_filters and not self.matches_category_filter(trans.get("category_path")):
                    continue
                
                filtered_transactions.append(trans)
            
            self.transactions = filtered_transactions
            logger.debug(f"After filtering: {len(self.transactions)} transactions")
            
            # Clear table completely
            self.transactions_table.clearContents()
            self.transactions_table.setRowCount(0)
            
            # Disable sorting while populating to prevent button disappearance
            self.transactions_table.setSortingEnabled(False)
            QApplication.processEvents()  # Process any pending events
            
            for i, trans in enumerate(self.transactions):
                self.transactions_table.insertRow(i)
                
                trans_id = trans.get("id")
                date = trans.get("date", "")[:10]
                desc = trans.get("description", "")
                trans_type = trans.get("transaction_type", "expense")
                amount_val = trans.get('amount', 0)
                
                # Format amount with R for Rands
                if trans_type == "income":
                    amount = f"+R{amount_val:.2f}"
                else:
                    amount = f"-R{amount_val:.2f}"
                
                category = trans.get("category_path", "(Uncategorized)")
                tags = ", ".join(trans.get("tags", []))
                
                # Create items
                date_item = QTableWidgetItem(date)
                desc_item = QTableWidgetItem(desc)
                amount_item = QTableWidgetItem(amount)
                category_item = QTableWidgetItem(category)
                tags_item = QTableWidgetItem(tags)
                
                # Color code income vs expense
                if trans_type == "income":
                    amount_item.setForeground(QColor(0, 150, 0))  # Green for income
                else:
                    amount_item.setForeground(QColor(200, 0, 0))  # Red for expense
                
                self.transactions_table.setItem(i, 0, date_item)
                self.transactions_table.setItem(i, 1, desc_item)
                self.transactions_table.setItem(i, 2, amount_item)
                self.transactions_table.setItem(i, 3, category_item)
                self.transactions_table.setItem(i, 4, tags_item)
                
                # Edit category button
                edit_cat_btn = QPushButton("✏️ Edit")
                edit_cat_btn.setToolTip("Edit transaction")
                edit_cat_btn.setMinimumWidth(80)
                edit_cat_btn.setStyleSheet("""
                    QPushButton {
                        padding: 4px 10px;
                        font-size: 13px;
                    }
                """)
                edit_cat_btn.clicked.connect(
                    self._make_edit_handler(trans_id)
                )
                self.transactions_table.setCellWidget(i, 5, edit_cat_btn)
                
                delete_btn = QPushButton("🗑️ Delete")
                delete_btn.setToolTip("Delete transaction")
                delete_btn.setMinimumWidth(80)
                delete_btn.setStyleSheet("""
                    QPushButton {
                        padding: 4px 10px;
                        font-size: 13px;
                    }
                """)
                delete_btn.clicked.connect(
                    self._make_delete_handler(trans_id)
                )
                self.transactions_table.setCellWidget(i, 6, delete_btn)
            
            # Re-enable sorting after all rows are added
            self.transactions_table.setSortingEnabled(True)
        except Exception as e:
            logger.exception(f"ERROR loading transactions: {e}")
            self.show_error(f"Failed to load transactions: {e}")
    
    def _make_delete_handler(self, transaction_id):
        """Create delete handler with proper closure."""
        def handler():
            self.delete_transaction(transaction_id)
        return handler
    
    def _make_edit_handler(self, transaction_id):
        """Create edit handler with proper closure."""
        def handler():
            self.edit_transaction(transaction_id)
        return handler

    def load_budgets(self):
        """Load and display budgets."""
        try:
            # Get actual budgets and their statuses
            # With a date range the backend pro-rates each budget to it;
            # otherwise it reports the current month/quarter/year.
            all_budgets = self.client.list_budgets()
            statuses = self.client.get_budget_status(self.active_date_from, self.active_date_to)
            
            self.budgets = all_budgets.get("budgets", [])
            self.budget_statuses = statuses.get("statuses", [])
            
            filtered_statuses = [
                status for status in self.budget_statuses
                if not self.active_category_filters or self.matches_category_filter(status.get("category_path"))
            ]
            
            self.budgets_table.setRowCount(0)
            
            # Disable sorting while populating to prevent button disappearance
            self.budgets_table.setSortingEnabled(False)
            
            for i, status in enumerate(filtered_statuses):
                self.budgets_table.insertRow(i)
                
                category = status.get("category_path") or "All"
                budget_amount = f"R{status.get('budget_amount', 0):.2f}"
                spent = f"R{status.get('spent_amount', 0):.2f}"
                
                percentage = status.get('percentage', 0)
                
                status_text = "OVER" if percentage >= 100 else ("WARNING" if percentage >= 75 else "OK")
                
                self.budgets_table.setItem(i, 0, QTableWidgetItem(category))
                self.budgets_table.setItem(i, 1, QTableWidgetItem(budget_amount))
                self.budgets_table.setItem(i, 2, QTableWidgetItem(spent))
                
                progress = QProgressBar()
                progress.setValue(int(min(percentage, 100)))
                if percentage >= 100:
                    progress.setStyleSheet("QProgressBar::chunk { background-color: #ff4444; }")
                elif percentage >= 75:
                    progress.setStyleSheet("QProgressBar::chunk { background-color: #ffaa00; }")
                self.budgets_table.setCellWidget(i, 3, progress)
                
                self.budgets_table.setItem(i, 4, QTableWidgetItem(status_text))
                
                edit_btn = QPushButton("✏️ Edit")
                edit_btn.setMinimumWidth(80)
                edit_btn.setStyleSheet("""
                    QPushButton {
                        padding: 4px 10px;
                        font-size: 13px;
                    }
                """)
                edit_btn.clicked.connect(
                    self._make_edit_budget_handler(status.get("budget_id"))
                )
                self.budgets_table.setCellWidget(i, 5, edit_btn)
                
                delete_btn = QPushButton("❌ Delete")
                delete_btn.setMinimumWidth(80)
                delete_btn.setStyleSheet("""
                    QPushButton {
                        padding: 4px 10px;
                        font-size: 13px;
                    }
                """)
                delete_btn.clicked.connect(
                    self._make_delete_budget_handler(status.get("budget_id"))
                )
                self.budgets_table.setCellWidget(i, 6, delete_btn)
            
            # Re-enable sorting after all rows are added
            self.budgets_table.setSortingEnabled(True)
            
        except Exception as e:
            self.show_error(f"Failed to load budgets: {e}")
    
    def _make_delete_budget_handler(self, budget_id):
        """Create delete budget handler with proper closure."""
        def handler():
            self.delete_budget(budget_id)
        return handler
    
    def _make_edit_budget_handler(self, budget_id):
        """Create edit budget handler with proper closure."""
        def handler():
            self.edit_budget(budget_id)
        return handler

    def load_unknowns(self):
        """Load and display uncategorized transactions."""
        try:
            data = self.client.get_unknown_transactions(limit=10000)
            unknowns = data.get("transactions", [])
            
            # Store unknowns for categorize function to access
            self.unknowns = unknowns
            
            # Clear table completely
            self.unknowns_table.clearContents()
            self.unknowns_table.setRowCount(0)
            
            # Disable sorting while populating to prevent button disappearance
            self.unknowns_table.setSortingEnabled(False)
            QApplication.processEvents()  # Process any pending events
            
            for i, trans in enumerate(unknowns):
                self.unknowns_table.insertRow(i)
                
                date = trans.get("date", "")[:10]
                desc = trans.get("description", "")
                trans_type = trans.get("transaction_type", "expense")
                amount_val = trans.get('amount', 0)
                
                # Format with Rands
                if trans_type == "income":
                    amount = f"+R{amount_val:.2f}"
                else:
                    amount = f"-R{amount_val:.2f}"
                
                self.unknowns_table.setItem(i, 0, QTableWidgetItem(date))
                self.unknowns_table.setItem(i, 1, QTableWidgetItem(desc))
                self.unknowns_table.setItem(i, 2, QTableWidgetItem(amount))
                
                edit_btn = QPushButton("🏷️ Categorize")
                edit_btn.setMinimumWidth(100)
                edit_btn.setStyleSheet("""
                    QPushButton {
                        padding: 4px 10px;
                        font-size: 13px;
                    }
                """)
                edit_btn.clicked.connect(
                    self._make_categorize_handler(trans.get("id"))
                )
                self.unknowns_table.setCellWidget(i, 3, edit_btn)
            
            # Re-enable sorting after all rows are added
            self.unknowns_table.setSortingEnabled(True)
        except Exception as e:
            self.show_error(f"Failed to load unknowns: {e}")
    
    def load_duplicates(self):
        """Load possible duplicate transactions (same date and amount)."""
        try:
            self.duplicates_table.clearContents()
            self.duplicates_table.setRowCount(0)
            
            # Disable sorting while populating to prevent button disappearance
            self.duplicates_table.setSortingEnabled(False)
            
            groups = self.client.get_duplicates().get("groups", [])
            rows = [(trans, group["transactions"]) for group in groups for trans in group["transactions"]]
            self.duplicates_table.setRowCount(len(rows))
            
            for i, (trans, group_transactions) in enumerate(rows):
                cells = [
                    trans.get("date", "")[:10],
                    trans.get("description", ""),
                    f"R{trans.get('amount', 0):.2f}",
                    f"{len(group_transactions)} matches",
                ]
                for col, text in enumerate(cells):
                    item = QTableWidgetItem(text)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.duplicates_table.setItem(i, col, item)
                
                keep_btn = QPushButton("✅ Keep")
                keep_btn.setMinimumWidth(80)
                keep_btn.setStyleSheet("QPushButton { padding: 4px 10px; font-size: 13px; }")
                keep_btn.clicked.connect(self._make_keep_duplicate_handler(trans.get("id"), group_transactions))
                self.duplicates_table.setCellWidget(i, 4, keep_btn)
                
                delete_btn = QPushButton("🗑️ Delete")
                delete_btn.setMinimumWidth(80)
                delete_btn.setStyleSheet("QPushButton { padding: 4px 10px; font-size: 13px; }")
                delete_btn.clicked.connect(self._make_delete_duplicate_handler(trans.get("id")))
                self.duplicates_table.setCellWidget(i, 5, delete_btn)
            
            self.duplicates_table.setSortingEnabled(True)
                
        except Exception as e:
            self.show_error(f"Failed to load duplicates: {e}")
    
    def _make_keep_duplicate_handler(self, transaction_id, group_transactions):
        """Create handler that marks a transaction as 'not a duplicate' of the rest of its group."""
        def handler():
            pairs = [[transaction_id, other["id"]] for other in group_transactions if other["id"] != transaction_id]
            try:
                self.client.ignore_duplicates(pairs)
                self.load_duplicates()
            except Exception as e:
                self.show_error(f"Failed to save ignored duplicate: {e}")
        return handler
    
    def load_merchants(self):
        """Load and display merchant relationships."""
        try:
            self.merchants_table.clearContents()
            self.merchants_table.setRowCount(0)
            
            # Disable sorting while populating to prevent button disappearance
            self.merchants_table.setSortingEnabled(False)
            QApplication.processEvents()
            
            # Get merchants from API
            data = self.client.list_merchants()
            merchants = data.get("merchants", [])
            
            if not merchants:
                return
            
            self.merchants_table.setRowCount(len(merchants))
            
            for i, merchant in enumerate(merchants):
                # Merchant name
                name_item = QTableWidgetItem(merchant.get("name", ""))
                name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
                self.merchants_table.setItem(i, 0, name_item)
                
                # Preferred category (what new transactions will be mapped to)
                preferred_cat = merchant.get("preferred_category") or merchant.get("default_category") or "None"
                category_item = QTableWidgetItem(preferred_cat)
                category_item.setFlags(category_item.flags() & ~Qt.ItemIsEditable)
                self.merchants_table.setItem(i, 1, category_item)
                
                # Confidence
                confidence = merchant.get("confidence", 1.0)
                confidence_item = QTableWidgetItem(f"{confidence:.0%}")
                confidence_item.setFlags(confidence_item.flags() & ~Qt.ItemIsEditable)
                self.merchants_table.setItem(i, 2, confidence_item)
                
                # Delete button
                delete_btn = QPushButton("🗑️ Delete")
                delete_btn.setMinimumWidth(80)
                delete_btn.setStyleSheet("""
                    QPushButton {
                        padding: 6px 12px;
                        font-size: 11px;
                    }
                """)
                delete_btn.clicked.connect(
                    self._make_delete_merchant_handler(merchant.get("id"))
                )
                self.merchants_table.setCellWidget(i, 3, delete_btn)
            
            # Re-enable sorting after all rows are added
            self.merchants_table.setSortingEnabled(True)
                
        except Exception as e:
            logger.exception(f"Failed to load merchants: {e}")
            self.show_error(f"Failed to load merchants: {e}")
    
    def _make_delete_merchant_handler(self, merchant_id):
        """Create handler to delete a merchant relationship."""
        def handler():
            try:
                reply = QMessageBox.question(
                    self,
                    "Confirm Delete",
                    "Delete this merchant relationship?\n\nFuture transactions from this merchant will need to be categorized again.",
                    QMessageBox.Yes | QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    self.client.delete_merchant(merchant_id)
                    self.show_info("Merchant relationship deleted")
                    self.load_merchants()
            except Exception as e:
                self.show_error(f"Failed to delete merchant: {e}")
        return handler

    def _make_delete_duplicate_handler(self, transaction_id):
        """Create handler to delete a duplicate transaction."""
        def handler():
            try:
                self.client.delete_transaction(transaction_id)
                self.load_duplicates()
                self.load_transactions()
                self.update_dashboard()
            except Exception as e:
                self.show_error(f"Failed to delete transaction: {e}")
        return handler
    
    def _make_categorize_handler(self, transaction_id):
        """Create categorize handler with proper closure."""
        def handler():
            self.categorize_transaction(transaction_id)
        return handler

    def new_transaction(self):
        """Create a new transaction with AI assistance."""
        category_names = self.category_paths()
        dialog = CreateTransactionDialog(self, category_names)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            
            # Validate required fields
            if not data.get("description"):
                self.show_error("Description is required")
                return
            
            if not data.get("amount"):
                self.show_error("Amount is required")
                return
            
            # Show loading
            progress = QProgressDialog("AI is processing your transaction...", None, 0, 0, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setAutoClose(True)
            progress.show()
            
            try:
                # Use smart endpoint - AI does all the work!
                result = self.client.smart_create_transaction(
                    description=data["description"],
                    amount=data["amount"]
                )
                progress.close()
                
                # Show what AI suggested
                suggestion = result.get("ai_suggestion", "")
                msg = result.get("message", "Transaction created!")
                if suggestion:
                    msg += f"\n\nℹ️ AI suggested category: {suggestion}"
                    msg += "\n\nCheck the 'Unknowns' tab to confirm or change the category."
                
                self.show_info(msg)
                self.load_transactions()
                self.load_unknowns()
            except Exception as e:
                progress.close()
                self.show_error(f"Failed to create transaction: {e}")


    def delete_transaction(self, transaction_id: str):
        """Delete a transaction."""
        logger.debug(f"Delete button clicked for transaction: {transaction_id}")
        if QMessageBox.question(self, "Confirm", "Delete this transaction?") == QMessageBox.Yes:
            try:
                logger.debug(f"Calling API to delete transaction: {transaction_id}")
                result = self.client.delete_transaction(transaction_id)
                logger.debug(f"Delete result: {result}")
                self.show_info("Transaction deleted successfully")
                logger.debug("Reloading transactions...")
                self.load_transactions()
                self.load_unknowns()
                self.update_dashboard()
                logger.debug("Reload complete")
            except Exception as e:
                logger.exception(f"ERROR deleting transaction: {e}")
                self.show_error(f"Failed to delete transaction: {e}")

    def edit_transaction(self, transaction_id: str):
        """Edit a transaction with full details."""
        logger.debug(f"Edit button clicked for transaction: {transaction_id}")
        
        # Find the transaction
        trans = next((t for t in self.transactions if t.get("id") == transaction_id), None)
        if not trans:
            self.show_error("Transaction not found")
            return
        
        # Open edit dialog with existing data
        category_names = self.category_paths()
        dialog = EditTransactionDialog(self, transaction=trans, categories=category_names)
        if dialog.exec():
            try:
                updated_data = dialog.get_data()
                logger.debug(f"Updating transaction {transaction_id} with: {updated_data}")
                
                # Call API to update (use **kwargs)
                result = self.client.update_transaction(transaction_id, **updated_data)
                logger.debug(f"Update result: {result}")
                
                self.show_info("Transaction updated successfully")
                
                # Clear table before reload to prevent button disappearance
                self.transactions_table.clearContents()
                self.transactions_table.setRowCount(0)
                QApplication.processEvents()
                
                self.load_transactions()
                self.load_unknowns()
                self.update_dashboard()
            except Exception as e:
                logger.exception(f"ERROR updating transaction: {e}")
                self.show_error(f"Failed to update transaction: {e}")

    def categorize_transaction(self, transaction_id: str):
        """Categorize an unknown transaction."""
        
        # Find the transaction in unknowns list (not filtered transactions)
        trans = next((t for t in self.unknowns if t.get("id") == transaction_id), None)
        if not trans:
            # Fallback: try to get from API
            try:
                all_trans = self.client.list_transactions(limit=1000)
                trans = next((t for t in all_trans.get("transactions", []) if t.get("id") == transaction_id), None)
            except:
                pass
        
        if not trans:
            self.show_error("Transaction not found")
            return
        
        category_names = self.category_paths()
        
        # Show simple category picker
        category, ok = QInputDialog.getItem(
            self,
            "Select Category",
            f"Categorize: {trans.get('description', '')} (R{trans.get('amount', 0)})",
            category_names,
            0,
            False
        )
        
        if ok and category:
            try:
                # Get the merchant/description for matching
                merchant_name = trans.get('description', '').strip().lower()
                
                # Categorize the selected transaction
                self.client.update_transaction(transaction_id, category_path=category)
                
                # Find and auto-categorize other unknowns with the same merchant
                matching_count = 0
                for other_trans in self.unknowns:
                    other_id = other_trans.get('id')
                    other_desc = other_trans.get('description', '').strip().lower()
                    
                    # Skip the one we just categorized
                    if other_id == transaction_id:
                        continue
                    
                    # If description matches, auto-categorize it
                    if other_desc == merchant_name:
                        try:
                            self.client.update_transaction(other_id, category_path=category)
                            matching_count += 1
                        except Exception as e:
                            logger.exception(f"Failed to auto-categorize {other_id}: {e}")
                
                # Show success message with count
                if matching_count > 0:
                    self.show_info(f"Transaction categorized as '{category}'\n\nAlso categorized {matching_count} other matching transaction(s)")
                else:
                    self.show_info(f"Transaction categorized as '{category}'")
                
                # Clear unknowns table before reload
                self.unknowns_table.clearContents()
                self.unknowns_table.setRowCount(0)
                QApplication.processEvents()
                
                self.load_transactions()
                self.load_unknowns()
            except Exception as e:
                self.show_error(f"Failed to update transaction: {e}")

    def new_budget(self):
        """Create a new budget."""
        category_names = self.category_paths()
        dialog = CreateBudgetDialog(self, category_names)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            logger.debug(f"Creating budget with data: {data}")
            try:
                result = self.client.create_budget(**data)
                logger.debug(f"Budget created: {result}")
                self.show_info("Budget created successfully")
                self.load_budgets()
                self.update_dashboard()
            except Exception as e:
                logger.exception(f"ERROR creating budget: {e}")
                self.show_error(f"Failed to create budget: {e}")

    def delete_budget(self, budget_id: str):
        """Delete a budget."""
        logger.debug(f"Delete budget called with ID: {budget_id}")
        if not budget_id:
            self.show_error("Cannot delete budget: No budget ID")
            return
        
        if QMessageBox.question(self, "Confirm", "Delete this budget?") == QMessageBox.Yes:
            try:
                logger.debug(f"Calling API to delete budget: {budget_id}")
                self.client.delete_budget(budget_id)
                self.show_info("Budget deleted successfully")
                self.load_budgets()
                self.update_dashboard()
            except Exception as e:
                logger.exception(f"ERROR deleting budget: {e}")
                self.show_error(f"Failed to delete budget: {e}")
    
    def edit_budget(self, budget_id: str):
        """Edit an existing budget."""
        # Find the budget
        budget = next((b for b in self.budgets if b.get("id") == budget_id), None)
        if not budget:
            self.show_error("Budget not found")
            return
        
        category_names = self.category_paths()
        
        # Create edit dialog with current values
        dialog = EditBudgetDialog(self, category_names, budget)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            try:
                # Update budget via API
                self.client.update_budget(budget_id, **data)
                self.show_info("Budget updated successfully")
                self.load_budgets()
                self.update_dashboard()
            except Exception as e:
                self.show_error(f"Failed to update budget: {e}")

    def new_category(self):
        """Create a new category."""
        # Extract category names from dict list
        category_names = [cat.get('name', '') for cat in self.categories_list if isinstance(cat, dict)]
        dialog = CreateCategoryDialog(self, category_names)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            try:
                self.client.create_category(**data)
                self.load_categories()
            except Exception as e:
                self.show_error(f"Failed to create category: {e}")

    def show_category_menu(self, position):
        """Show context menu for category."""
        item = self.category_tree.itemAt(position)
        if not item:
            return
        
        menu = QMenu()
        
        # Get category ID from item data
        category_id = item.data(0, Qt.UserRole)
        category_name = item.text(0)
        
        if category_id:
            delete_action = menu.addAction(f"🗑️ Delete '{category_name}'")
            delete_action.triggered.connect(lambda: self.delete_category(category_id, category_name))
            menu.addSeparator()
        
        menu.addAction("Expand All", lambda: self.category_tree.expandAll())
        menu.addAction("Collapse All", lambda: self.category_tree.collapseAll())
        menu.exec(self.category_tree.mapToGlobal(position))
    
    def delete_category(self, category_id: str, category_name: str):
        """Delete a category and all its children."""
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete category '{category_name}' and all its subcategories?\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.client.delete_category(category_id)
                self.show_info(f"Category '{category_name}' deleted successfully")
                self.load_categories()
            except Exception as e:
                self.show_error(f"Failed to delete category: {e}")

    def import_csv(self):
        """Import transactions from CSV."""
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CSV File",
            "",
            "CSV Files (*.csv)"
        )
        
        if not file_path:
            return
        try:
            # Bank exports are often not UTF-8; don't fail on the odd stray byte.
            with open(file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
                csv_content = f.read()
        except OSError as e:
            self.show_error(f"Failed to read CSV: {e}")
            return

        progress = QProgressDialog("Importing and categorizing transactions...\nThis may take a few minutes for large files.", None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        try:
            result = self.client.import_bank_csv(csv_content, bank_format="generic")
        except Exception as e:
            progress.close()
            self.show_error(f"Failed to import CSV: {e}")
            return
        progress.close()

        lines = [
            f"Imported: {result.get('imported', 0)}",
            f"Already in ledger (skipped): {result.get('duplicates', 0)}",
            f"Unreadable rows (skipped): {result.get('skipped', 0)}",
            f"Categorized from learned merchants: {result.get('learned_categorised', 0)}",
            f"Categorized by AI: {result.get('ai_categorised', 0)}",
        ]
        if result.get('ai_error'):
            lines.append(f"\nAI categorization was skipped: {result['ai_error']}")
        message = "\n".join(lines)
        self.import_status.setText(message)
        self.show_info(message)
        self.load_transactions()
        self.load_unknowns()
        self.load_duplicates()
        self.update_dashboard()

    # ============ UTILITY METHODS ============

    def show_error(self, message: str):
        """Show error message."""
        QMessageBox.critical(self, "Error", message)

    def show_info(self, message: str):
        """Show info message."""
        QMessageBox.information(self, "Info", message)

    def closeEvent(self, event):
        """Clean up when closing."""
        self.client.close()
        event.accept()
    
    def update_dashboard(self):
        """Update dashboard charts and statistics."""
        try:
            
            # Calculate statistics
            total_income = sum(t.get('amount', 0) for t in self.transactions if t.get('transaction_type') == 'income')
            total_expenses = sum(t.get('amount', 0) for t in self.transactions if t.get('transaction_type') == 'expense')
            net_balance = total_income - total_expenses
            
            # Calculate average daily spending
            if self.transactions:
                dates = [datetime.fromisoformat(t.get('date', '').replace('Z', '+00:00')) 
                        for t in self.transactions if t.get('date')]
                if dates:
                    days_range = max(1, (max(dates) - min(dates)).days + 1)
                    avg_daily = total_expenses / days_range
                else:
                    avg_daily = 0
            else:
                avg_daily = 0
            
            # Update stats labels
            self.total_income_label.setText(f"<b>Total Income:</b> <span style='color: green;'>R{total_income:,.2f}</span>")
            self.total_expenses_label.setText(f"<b>Total Expenses:</b> <span style='color: red;'>R{total_expenses:,.2f}</span>")
            
            balance_color = 'green' if net_balance >= 0 else 'red'
            self.net_balance_label.setText(f"<b>Net Balance:</b> <span style='color: {balance_color};'>R{net_balance:,.2f}</span>")
            self.avg_daily_label.setText(f"<b>Avg Daily Spend:</b> <span style='color: #666;'>R{avg_daily:,.2f}</span>")
            
            # Chart 1: Spending by Category (Pie Chart) with Drill-Down
            category_spending = {}
            
            # Build category lookup map
            category_map = {}
            root_category_names = set()
            
            for cat in self.categories_list:
                cat_id = cat.get('id', '')
                cat_name = cat.get('name', '')
                parent_id = cat.get('parent_id')
                category_map[cat_name.lower()] = {
                    'id': cat_id,
                    'name': cat_name,
                    'parent_id': parent_id,
                    'path': cat.get('path', cat_name)
                }
                # Track root categories (no parent)
                if not parent_id:
                    root_category_names.add(cat_name)
            
            # Show all expenses by root category (no drill-down)
            for trans in self.transactions:
                if trans.get('transaction_type') == 'expense':
                    cat = trans.get('category_path', 'Uncategorized')
                    if not cat:
                        continue
                        
                    # Root level - show root categories only
                    if '/' in cat:
                        # Has path like "Food & Dining/Groceries" - take first part
                        display_cat = cat.split('/')[0]
                    else:
                            # Single category name - check if it's a root or needs parent lookup
                            cat_lower = cat.lower()
                            if cat_lower in category_map:
                                parent_id = category_map[cat_lower].get('parent_id')
                                if parent_id:
                                    # It's a subcategory, find root parent
                                    for parent_cat in self.categories_list:
                                        if parent_cat.get('id') == parent_id:
                                            # Check if this parent is root or has a parent
                                            if not parent_cat.get('parent_id'):
                                                display_cat = parent_cat.get('name', cat)
                                            else:
                                                # Keep traversing up to find root
                                                current_check_id = parent_id
                                                while current_check_id:
                                                    found_parent = next((c for c in self.categories_list if c.get('id') == current_check_id), None)
                                                    if found_parent:
                                                        if not found_parent.get('parent_id'):
                                                            display_cat = found_parent.get('name', cat)
                                                            break
                                                        current_check_id = found_parent.get('parent_id')
                                                    else:
                                                        display_cat = cat
                                                        break
                                            break
                                    else:
                                        display_cat = cat
                                else:
                                    # It's already a root category
                                    display_cat = cat
                            else:
                                # Unknown category, use as-is
                                display_cat = cat
                    
                    category_spending[display_cat] = category_spending.get(display_cat, 0) + trans.get('amount', 0)
            
            if category_spending:
                # Sort by spending and take top 8
                sorted_cats = sorted(category_spending.items(), key=lambda x: x[1], reverse=True)[:8]
                labels = [f"{cat.split('/')[-1]}\nR{amt:,.0f}" for cat, amt in sorted_cats]  # Show only last part of path
                sizes = [amount for _, amount in sorted_cats]
                
                # Store slice data for click detection (category, size)
                
                fig, ax = plt.subplots(figsize=(7, 5.5), facecolor='white')
                fig.patch.set_facecolor('white')
                # Use our color palette for consistent branding
                colors = COLOR_PALETTE['chart_colors']
                wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%', 
                                                   colors=colors, startangle=90,
                                                   textprops={'fontsize': 10, 'color': COLOR_PALETTE['text']})
                for autotext in autotexts:
                    autotext.set_color('white')
                    autotext.set_fontweight('bold')
                    autotext.set_fontsize(9)
                
                # Set title with purple color
                ax.set_title('Spending by Category', fontsize=14, fontweight='bold', 
                           pad=20, color=COLOR_PALETTE['primary_dark'])
                
                # Save to buffer and display
                buf = BytesIO()
                plt.tight_layout()
                fig.savefig(buf, format='png', dpi=90, bbox_inches='tight')
                buf.seek(0)
                pixmap = QPixmap()
                pixmap.loadFromData(buf.read())
                self.category_chart_label.setPixmap(pixmap.scaled(
                    self.category_chart_label.width(),
                    self.category_chart_label.height(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                ))
                plt.close(fig)
            else:
                self.category_chart_label.setText("<center><br><br><b>No spending data yet</b><br>Add transactions to see charts</center>")
            
            # Chart 2: Spending Over Time (Line Chart)
            if self.transactions:
                daily_spending = defaultdict(float)
                daily_income = defaultdict(float)
                
                for trans in self.transactions:
                    if trans.get('date'):
                        date_obj = datetime.fromisoformat(trans.get('date', '').replace('Z', '+00:00'))
                        date_key = date_obj.date()
                        amount = trans.get('amount', 0)
                        
                        if trans.get('transaction_type') == 'expense':
                            daily_spending[date_key] += amount
                        else:
                            daily_income[date_key] += amount
                
                if daily_spending or daily_income:
                    # Get all dates in range
                    all_dates = sorted(set(list(daily_spending.keys()) + list(daily_income.keys())))
                    
                    spending_values = [daily_spending.get(d, 0) for d in all_dates]
                    income_values = [daily_income.get(d, 0) for d in all_dates]
                    
                    fig, ax = plt.subplots(figsize=(7, 5.5), facecolor='white')
                    fig.patch.set_facecolor('white')
                    ax.set_facecolor('#fafbff')
                    ax.plot(all_dates, spending_values, marker='o', linestyle='-', 
                           color=COLOR_PALETTE['danger'], linewidth=3, label='Expenses', markersize=6, alpha=0.9)
                    ax.plot(all_dates, income_values, marker='s', linestyle='-', 
                           color=COLOR_PALETTE['primary'], linewidth=3, label='Income', markersize=6, alpha=0.9)
                    
                    ax.set_xlabel('Date', fontsize=11, color=COLOR_PALETTE['text'])
                    ax.set_ylabel('Amount (R)', fontsize=11, color=COLOR_PALETTE['text'])
                    ax.set_title('Spending Over Time', fontsize=14, fontweight='bold', 
                               pad=20, color=COLOR_PALETTE['primary_dark'])
                    ax.legend(loc='upper left', fontsize=10, framealpha=0.9)
                    ax.grid(True, alpha=0.2, color=COLOR_PALETTE['border'])
                    ax.tick_params(colors=COLOR_PALETTE['text'])
                    plt.xticks(rotation=45, ha='right', fontsize=9)
                    plt.yticks(fontsize=10)
                    
                    buf = BytesIO()
                    plt.tight_layout()
                    fig.savefig(buf, format='png', dpi=90, bbox_inches='tight')
                    buf.seek(0)
                    pixmap = QPixmap()
                    pixmap.loadFromData(buf.read())
                    self.spending_time_chart.setPixmap(pixmap.scaled(
                        self.spending_time_chart.width(),
                        self.spending_time_chart.height(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    ))
                    plt.close(fig)
                else:
                    self.spending_time_chart.setText("<center><br><br><b>No time data yet</b><br>Add transactions to see trends</center>")
            else:
                self.spending_time_chart.setText("<center><br><br><b>No time data yet</b><br>Add transactions to see trends</center>")
            
            # Chart 3: Budget Progress (Bar Chart)
            chart_statuses = self.budget_statuses[:6]  # Top 6 budgets
            if chart_statuses:
                budget_names = [s.get('category_path') or 'All' for s in chart_statuses]
                budget_limits = [s.get('budget_amount', 0) for s in chart_statuses]
                budget_spent = [s.get('spent_amount', 0) for s in chart_statuses]
                
                fig, ax = plt.subplots(figsize=(7, 5.5), facecolor='white')
                fig.patch.set_facecolor('white')
                ax.set_facecolor('#fafbff')
                x = range(len(budget_names))
                width = 0.35
                
                # Use color palette for budget vs spent bars
                ax.bar([i - width/2 for i in x], budget_limits, width, label='Budget', 
                              color=COLOR_PALETTE['primary'], alpha=0.8, edgecolor=COLOR_PALETTE['primary_dark'], linewidth=1.5)
                ax.bar([i + width/2 for i in x], budget_spent, width, label='Spent', 
                              color=COLOR_PALETTE['warning'], alpha=0.8, edgecolor=COLOR_PALETTE['danger'], linewidth=1.5)
                
                # Add value labels on bars
                for i, (limit, spent) in enumerate(zip(budget_limits, budget_spent)):
                    if limit > 0:
                        pct = (spent / limit) * 100
                        color = COLOR_PALETTE['danger'] if pct > 100 else COLOR_PALETTE['success']
                        ax.text(i, max(limit, spent) + max(budget_limits) * 0.03, f'{pct:.0f}%', 
                               ha='center', fontsize=9, fontweight='bold', color=color)
                
                ax.set_ylabel('Amount (R)', fontsize=11, color=COLOR_PALETTE['text'])
                ax.set_title('Budget vs Spending', fontsize=14, fontweight='bold', 
                           pad=20, color=COLOR_PALETTE['primary_dark'])
                ax.set_xticks(x)
                ax.set_xticklabels(budget_names, rotation=45, ha='right', fontsize=9)
                ax.legend(fontsize=10, framealpha=0.9)
                ax.grid(axis='y', alpha=0.2, color=COLOR_PALETTE['border'])
                ax.tick_params(colors=COLOR_PALETTE['text'])
                plt.yticks(fontsize=10)
                
                buf = BytesIO()
                plt.tight_layout()
                fig.savefig(buf, format='png', dpi=90, bbox_inches='tight')
                buf.seek(0)
                pixmap = QPixmap()
                pixmap.loadFromData(buf.read())
                self.budget_chart_label.setPixmap(pixmap.scaled(
                    self.budget_chart_label.width(),
                    self.budget_chart_label.height(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                ))
                plt.close(fig)
            else:
                self.budget_chart_label.setText("<center><br><br><b>No budgets yet</b><br>Create budgets to track spending</center>")
            
            # Chart 4: Top Spending Categories (Horizontal Bar)
            if category_spending:
                # Sort and take top 10
                sorted_cats = sorted(category_spending.items(), key=lambda x: x[1], reverse=True)[:10]
                categories = [cat for cat, _ in sorted_cats]
                amounts = [amount for _, amount in sorted_cats]
                
                fig, ax = plt.subplots(figsize=(7, 5.5), facecolor='white')
                fig.patch.set_facecolor('white')
                ax.set_facecolor('#fafbff')
                y_pos = range(len(categories))
                
                # Use our color palette with gradient from primary to warning
                cmap = mcolors.LinearSegmentedColormap.from_list(
                    'budget_gradient', 
                    [COLOR_PALETTE['primary_dark'], COLOR_PALETTE['primary'], COLOR_PALETTE['primary_light']]
                )
                colors_list = [cmap(i / max(1, len(categories)-1)) for i in range(len(categories))]
                bars = ax.barh(y_pos, amounts, color=colors_list, alpha=0.9, 
                             edgecolor=COLOR_PALETTE['primary_dark'], linewidth=1)
                
                # Add value labels
                for i, (bar, amount) in enumerate(zip(bars, amounts)):
                    width = bar.get_width()
                    ax.text(width + max(amounts) * 0.01, bar.get_y() + bar.get_height()/2, 
                           f'R{amount:,.0f}', ha='left', va='center', fontsize=9, 
                           fontweight='bold', color=COLOR_PALETTE['primary_dark'])
                
                ax.set_yticks(y_pos)
                ax.set_yticklabels(categories, fontsize=10)
                ax.set_xlabel('Amount (R)', fontsize=11, color=COLOR_PALETTE['text'])
                ax.set_title('Top Spending Categories', fontsize=14, fontweight='bold', 
                           pad=20, color=COLOR_PALETTE['primary_dark'])
                ax.grid(axis='x', alpha=0.2, color=COLOR_PALETTE['border'])
                ax.tick_params(colors=COLOR_PALETTE['text'])
                plt.xticks(fontsize=10)
                
                buf = BytesIO()
                plt.tight_layout()
                fig.savefig(buf, format='png', dpi=90, bbox_inches='tight')
                buf.seek(0)
                pixmap = QPixmap()
                pixmap.loadFromData(buf.read())
                self.top_categories_chart.setPixmap(pixmap.scaled(
                    self.top_categories_chart.width(),
                    self.top_categories_chart.height(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                ))
                plt.close(fig)
            else:
                self.top_categories_chart.setText("<center><br><br><b>No spending data yet</b><br>Add transactions to see top categories</center>")
            
            # Chart 5: Income by Category (Pie Chart)
            income_spending = {}
            for trans in self.transactions:
                if trans.get('transaction_type') == 'income':
                    cat = trans.get('category_path', 'Other Income')
                    if not cat:
                        cat = 'Other Income'
                    # Get root category
                    if '/' in cat:
                        cat = cat.split('/')[0]
                    income_spending[cat] = income_spending.get(cat, 0) + trans.get('amount', 0)
            
            if income_spending:
                sorted_income = sorted(income_spending.items(), key=lambda x: x[1], reverse=True)[:8]
                labels = [f"{cat}\nR{amt:,.0f}" for cat, amt in sorted_income]
                sizes = [amount for _, amount in sorted_income]
                
                fig, ax = plt.subplots(figsize=(7, 5.5), facecolor='white')
                fig.patch.set_facecolor('white')
                # Use primary/success colors for income
                colors = [COLOR_PALETTE['success'], COLOR_PALETTE['primary'], COLOR_PALETTE['info'], 
                         COLOR_PALETTE['primary_light'], COLOR_PALETTE['accent_indigo']] + COLOR_PALETTE['chart_colors'][:3]
                wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%',
                                                   colors=colors, startangle=90,
                                                   textprops={'fontsize': 10, 'color': COLOR_PALETTE['text']})
                for autotext in autotexts:
                    autotext.set_color('white')
                    autotext.set_fontweight('bold')
                    autotext.set_fontsize(9)
                
                ax.set_title('Income by Source', fontsize=14, fontweight='bold', 
                           pad=20, color=COLOR_PALETTE['primary_dark'])
                
                buf = BytesIO()
                plt.tight_layout()
                fig.savefig(buf, format='png', dpi=90, bbox_inches='tight')
                buf.seek(0)
                pixmap = QPixmap()
                pixmap.loadFromData(buf.read())
                self.income_chart_label.setPixmap(pixmap.scaled(
                    self.income_chart_label.width(),
                    self.income_chart_label.height(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                ))
                plt.close(fig)
            else:
                self.income_chart_label.setText("<center><br><br><b>No income data yet</b><br>Add income transactions</center>")
                
        except Exception as e:
            logger.exception(f"Error updating dashboard: {e}")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    app = QApplication(sys.argv)
    window = BudgetAppMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

