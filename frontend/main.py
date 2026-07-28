"""
PySide6 desktop frontend for the Budget App.
"""
import sys
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem,
    QLabel, QPushButton, QLineEdit, QComboBox, QSpinBox, QDateEdit,
    QDialog, QDialogButtonBox, QFormLayout, QMessageBox, QProgressBar,
    QHeaderView, QMenu, QSplitter, QListWidget, QListWidgetItem, QGroupBox,
    QGraphicsOpacityEffect, QSizePolicy
)
from PySide6.QtCore import Qt, QDate, QTimer, QThread, Signal, QObject, QPropertyAnimation, QEasingCurve, QSize, QRect, QPoint
from PySide6.QtGui import QColor, QIcon

from api_client import BudgetAppClient


# ============ COLOR PALETTE ============

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
        
        print(f"Drop detected: Category {dragged_category_id} -> Parent {new_parent_id}")
        
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
        current_cat = self.budget.get("category_path", "(Any)")
        if current_cat:
            index = self.category_combo.findText(current_cat)
            if index >= 0:
                self.category_combo.setCurrentIndex(index)
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
            from datetime import datetime
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
        from PySide6.QtWidgets import QScrollArea
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
        from PySide6.QtWidgets import QGridLayout, QScrollArea
        
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
            
            def add_node(parent_id, parent_widget=None):
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
                    
                    # Store full node with all properties
                    self.categories_list.append({
                        'id': parent_id,
                        'name': node.get('name', ''),
                        'parent_id': node.get('parent_id'),
                        'path': node.get('name', ''),
                        'icon': node.get('icon', '')
                    })
                    
                    for child_id in node.get("children", []):
                        add_node(child_id, item)
            
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
            from PySide6.QtWidgets import QCheckBox
            
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
            print(f"Failed to update category filter: {e}")
    
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
        """Handle category drag-and-drop via custom signal."""
        print(f"\n=== CATEGORY MOVED SIGNAL ===")
        print(f"Category ID: {category_id}")
        print(f"New Parent ID: {new_parent_id}")
        
        try:
            # Update via API
            result = self.client.update_category({
                'id': category_id,
                'parent_id': new_parent_id
            })
            print(f"API update successful: {result}")
            
            self.show_info("Category moved successfully")
            # Reload to reflect changes
            QTimer.singleShot(100, self.load_categories)  # Small delay to let tree settle
        except Exception as e:
            print(f"Error moving category: {e}")
            import traceback
            traceback.print_exc()
            self.show_error(f"Failed to move category: {e}")
            self.load_categories()  # Reload to revert
    
    def on_category_moved(self, parent, start, end, destination, row):
        """Legacy handler for rowsMoved signal (kept for compatibility)."""
        print(f"\n=== DRAG DROP EVENT FIRED (rowsMoved) ===")
        print(f"parent: {parent}, start: {start}, end: {end}, destination: {destination}, row: {row}")

    def load_transactions(self):
        """Load and display transactions."""
        try:
            print("Loading transactions from API...")
            data = self.client.list_transactions(limit=10000)
            all_transactions = data.get("transactions", [])
            print(f"Loaded {len(all_transactions)} transactions")
            
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
                if self.active_category_filters:
                    # Get selected category names from filter
                    selected_names = []
                    for i in range(self.category_filter_list.count()):
                        item = self.category_filter_list.item(i)
                        if item.isSelected():
                            selected_names.append(item.text())
                    
                    if selected_names:
                        # Check if transaction's category_path starts with any selected category
                        trans_cat = trans.get("category_path", "")
                        if not trans_cat:
                            continue
                        
                        # Check if any selected category matches
                        category_matches = False
                        for selected_name in selected_names:
                            # Match if category_path equals or starts with selected category
                            if trans_cat == selected_name or trans_cat.startswith(selected_name + "/"):
                                category_matches = True
                                break
                        
                        if not category_matches:
                            continue
                
                filtered_transactions.append(trans)
            
            self.transactions = filtered_transactions
            print(f"After filtering: {len(self.transactions)} transactions")
            
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
            print(f"ERROR loading transactions: {e}")
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
            all_budgets = self.client.list_budgets()
            statuses = self.client.get_budget_status()
            
            # Store both for use in charts and display
            self.budgets = all_budgets.get("budgets", [])
            self.budget_statuses = statuses.get("statuses", [])
            
            # Calculate scaling factor based on date range
            scale_factor = self._calculate_budget_scale_factor()
            
            # Apply category filter
            filtered_statuses = []
            for status in self.budget_statuses:
                if self.active_category_filters:
                    # Get the budget to check its category
                    budget = next((b for b in self.budgets if b.get("id") == status.get("budget_id")), None)
                    if budget:
                        budget_cat_id = budget.get("category_id")
                        if budget_cat_id not in self.active_category_filters:
                            continue
                
                # Scale the budget amounts
                scaled_status = status.copy()
                scaled_status["budget_amount"] = status.get("budget_amount", 0) * scale_factor
                filtered_statuses.append(scaled_status)
            
            self.budgets_table.setRowCount(0)
            
            # Disable sorting while populating to prevent button disappearance
            self.budgets_table.setSortingEnabled(False)
            
            for i, status in enumerate(filtered_statuses):
                self.budgets_table.insertRow(i)
                
                category = status.get("category_path", "All")
                budget_amount = f"R{status.get('budget_amount', 0):.2f}"
                spent = f"R{status.get('spent_amount', 0):.2f}"
                
                # Recalculate percentage with scaled budget
                scaled_budget = status.get('budget_amount', 0)
                spent_val = status.get('spent_amount', 0)
                percentage = (spent_val / scaled_budget * 100) if scaled_budget > 0 else 0
                
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
    
    def _calculate_budget_scale_factor(self):
        """Calculate budget scaling factor based on active date range."""
        if not self.active_date_from or not self.active_date_to:
            return 1.0  # No scaling if no date range selected
        
        from datetime import datetime
        try:
            date_from = datetime.strptime(self.active_date_from, "%Y-%m-%d")
            date_to = datetime.strptime(self.active_date_to, "%Y-%m-%d")
            
            # Calculate days in selected range
            days_selected = (date_to - date_from).days + 1
            
            # Assume budgets are monthly (30 days)
            days_in_period = 30
            
            # Scale factor
            scale_factor = days_selected / days_in_period
            
            print(f"Budget scaling: {days_selected} days selected / {days_in_period} days = {scale_factor:.2f}x")
            return scale_factor
            
        except Exception as e:
            print(f"Error calculating budget scale: {e}")
            return 1.0
    
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
        """Load possible duplicate transactions."""
        try:
            self.duplicates_table.clearContents()
            
            # Disable sorting while populating to prevent button disappearance
            self.duplicates_table.setSortingEnabled(False)
            QApplication.processEvents()
            
            # Load ignored duplicates
            import json
            import os
            ignored_file = os.path.join(os.path.dirname(__file__), "..", "backend", "data", "ignored_duplicates.json")
            ignored_pairs = set()
            try:
                if os.path.exists(ignored_file):
                    with open(ignored_file, 'r') as f:
                        ignored_list = json.load(f)
                        # Convert list of pairs to set of tuples for fast lookup
                        ignored_pairs = {(pair[0], pair[1]) for pair in ignored_list}
            except Exception as e:
                print(f"Could not load ignored duplicates: {e}")
            
            # Get all transactions
            data = self.client.list_transactions(limit=1000)
            transactions = data.get("transactions", [])
            if not transactions:
                self.duplicates_table.setRowCount(0)
                return
            
            # Group by date + amount to find duplicates
            from collections import defaultdict
            groups = defaultdict(list)
            for trans in transactions:
                key = (trans.get("date"), trans.get("amount"))
                groups[key].append(trans)
            
            # Filter to only groups with 2+ items
            duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}
            
            # Flatten groups for display, excluding ignored pairs
            rows = []
            for (date, amount), trans_list in duplicate_groups.items():
                # Filter out ignored transactions from this group
                filtered_trans_list = []
                for trans in trans_list:
                    trans_id = trans.get("id")
                    # Check if this transaction is ignored with any other in the group
                    is_ignored = any(
                        (trans_id, other.get("id")) in ignored_pairs or 
                        (other.get("id"), trans_id) in ignored_pairs
                        for other in trans_list if other.get("id") != trans_id
                    )
                    if not is_ignored:
                        filtered_trans_list.append(trans)
                
                # Only show group if still has 2+ non-ignored items
                if len(filtered_trans_list) >= 2:
                    for trans in filtered_trans_list:
                        rows.append({
                            "transaction": trans,
                            "match_count": len(filtered_trans_list),
                            "group_transactions": filtered_trans_list
                        })
            
            if not rows:
                self.duplicates_table.setRowCount(0)
                return
            
            self.duplicates_table.setRowCount(len(rows))
            
            for i, row in enumerate(rows):
                trans = row["transaction"]
                match_count = row["match_count"]
                
                # Date
                date_item = QTableWidgetItem(trans.get("date", ""))
                date_item.setFlags(date_item.flags() & ~Qt.ItemIsEditable)
                self.duplicates_table.setItem(i, 0, date_item)
                
                # Description
                desc_item = QTableWidgetItem(trans.get("description", ""))
                desc_item.setFlags(desc_item.flags() & ~Qt.ItemIsEditable)
                self.duplicates_table.setItem(i, 1, desc_item)
                
                # Amount
                amount_item = QTableWidgetItem(f"R{trans.get('amount', 0):.2f}")
                amount_item.setFlags(amount_item.flags() & ~Qt.ItemIsEditable)
                self.duplicates_table.setItem(i, 2, amount_item)
                
                # Match count
                match_item = QTableWidgetItem(f"{match_count} matches")
                match_item.setFlags(match_item.flags() & ~Qt.ItemIsEditable)
                self.duplicates_table.setItem(i, 3, match_item)
                
                # Keep button - store group info in button
                keep_btn = QPushButton("✅ Keep")
                keep_btn.setMinimumWidth(80)
                keep_btn.setStyleSheet("""
                    QPushButton {
                        padding: 4px 10px;
                        font-size: 13px;
                    }
                """)
                keep_btn.clicked.connect(
                    self._make_keep_duplicate_handler(trans.get("id"), row["group_transactions"])
                )
                self.duplicates_table.setCellWidget(i, 4, keep_btn)
                
                # Delete button
                delete_btn = QPushButton("🗑️ Delete")
                delete_btn.setMinimumWidth(80)
                delete_btn.setStyleSheet("""
                    QPushButton {
                        padding: 4px 10px;
                        font-size: 13px;
                    }
                """)
                delete_btn.clicked.connect(
                    self._make_delete_duplicate_handler(trans.get("id"))
                )
                self.duplicates_table.setCellWidget(i, 5, delete_btn)
            
            # Re-enable sorting after all rows are added
            self.duplicates_table.setSortingEnabled(True)
                
        except Exception as e:
            self.show_error(f"Failed to load duplicates: {e}")
    
    def _make_keep_duplicate_handler(self, transaction_id, group_transactions):
        """Create handler to mark duplicate as kept (save as not duplicate)."""
        def handler():
            import json
            import os
            try:
                ignored_file = os.path.join(os.path.dirname(__file__), "..", "backend", "data", "ignored_duplicates.json")
                
                # Load existing ignored pairs
                ignored_list = []
                if os.path.exists(ignored_file):
                    with open(ignored_file, 'r') as f:
                        ignored_list = json.load(f)
                
                # Add all pairs between this transaction and others in group
                for other_trans in group_transactions:
                    other_id = other_trans.get("id")
                    if other_id != transaction_id:
                        # Store as sorted pair to avoid duplicates
                        pair = tuple(sorted([transaction_id, other_id]))
                        if list(pair) not in ignored_list:
                            ignored_list.append(list(pair))
                
                # Save back
                with open(ignored_file, 'w') as f:
                    json.dump(ignored_list, f, indent=2)
                
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
            print(f"Failed to load merchants: {e}")
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
        category_names = [cat.get('name', cat) if isinstance(cat, dict) else cat for cat in self.categories_list]
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
            from PySide6.QtWidgets import QProgressDialog
            from PySide6.QtCore import Qt
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
        print(f"Delete button clicked for transaction: {transaction_id}")
        if QMessageBox.question(self, "Confirm", "Delete this transaction?") == QMessageBox.Yes:
            try:
                print(f"Calling API to delete transaction: {transaction_id}")
                result = self.client.delete_transaction(transaction_id)
                print(f"Delete result: {result}")
                self.show_info("Transaction deleted successfully")
                print("Reloading transactions...")
                self.load_transactions()
                self.load_unknowns()
                self.update_dashboard()
                print("Reload complete")
            except Exception as e:
                print(f"ERROR deleting transaction: {e}")
                import traceback
                traceback.print_exc()
                self.show_error(f"Failed to delete transaction: {e}")

    def edit_transaction(self, transaction_id: str):
        """Edit a transaction with full details."""
        print(f"Edit button clicked for transaction: {transaction_id}")
        
        # Find the transaction
        trans = next((t for t in self.transactions if t.get("id") == transaction_id), None)
        if not trans:
            self.show_error("Transaction not found")
            return
        
        # Open edit dialog with existing data
        category_names = [cat.get('name', cat) if isinstance(cat, dict) else cat for cat in self.categories_list]
        dialog = EditTransactionDialog(self, transaction=trans, categories=category_names)
        if dialog.exec():
            try:
                updated_data = dialog.get_data()
                print(f"Updating transaction {transaction_id} with: {updated_data}")
                
                # Call API to update (use **kwargs)
                result = self.client.update_transaction(transaction_id, **updated_data)
                print(f"Update result: {result}")
                
                self.show_info("Transaction updated successfully")
                
                # Clear table before reload to prevent button disappearance
                self.transactions_table.clearContents()
                self.transactions_table.setRowCount(0)
                QApplication.processEvents()
                
                self.load_transactions()
                self.load_unknowns()
                self.update_dashboard()
            except Exception as e:
                print(f"ERROR updating transaction: {e}")
                import traceback
                traceback.print_exc()
                self.show_error(f"Failed to update transaction: {e}")

    def categorize_transaction(self, transaction_id: str):
        """Categorize an unknown transaction."""
        from PySide6.QtWidgets import QInputDialog
        
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
        
        # Extract category names from dict list
        category_names = [cat.get('name', '') for cat in self.categories_list if isinstance(cat, dict)]
        
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
                            print(f"Failed to auto-categorize {other_id}: {e}")
                
                # Show success message with count
                if matching_count > 0:
                    self.show_info(f"Transaction categorized as '{category}'\\n\\nAlso categorized {matching_count} other matching transaction(s)")
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
        # Extract category names from dict list
        category_names = [cat.get('name', '') for cat in self.categories_list if isinstance(cat, dict)]
        dialog = CreateBudgetDialog(self, category_names)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            print(f"Creating budget with data: {data}")
            try:
                result = self.client.create_budget(**data)
                print(f"Budget created: {result}")
                self.show_info("Budget created successfully")
                self.load_budgets()
                self.update_dashboard()
            except Exception as e:
                print(f"ERROR creating budget: {e}")
                import traceback
                traceback.print_exc()
                self.show_error(f"Failed to create budget: {e}")

    def delete_budget(self, budget_id: str):
        """Delete a budget."""
        print(f"Delete budget called with ID: {budget_id}")
        if not budget_id:
            self.show_error("Cannot delete budget: No budget ID")
            return
        
        if QMessageBox.question(self, "Confirm", "Delete this budget?") == QMessageBox.Yes:
            try:
                print(f"Calling API to delete budget: {budget_id}")
                self.client.delete_budget(budget_id)
                self.show_info("Budget deleted successfully")
                self.load_budgets()
                self.update_dashboard()
            except Exception as e:
                print(f"ERROR deleting budget: {e}")
                import traceback
                traceback.print_exc()
                self.show_error(f"Failed to delete budget: {e}")
    
    def edit_budget(self, budget_id: str):
        """Edit an existing budget."""
        # Find the budget
        budget = next((b for b in self.budgets if b.get("id") == budget_id), None)
        if not budget:
            self.show_error("Budget not found")
            return
        
        # Extract category names
        category_names = [cat.get('name', '') for cat in self.categories_list if isinstance(cat, dict)]
        
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
        from PySide6.QtWidgets import QFileDialog, QProgressDialog
        from PySide6.QtCore import Qt
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CSV File",
            "",
            "CSV Files (*.csv)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    csv_content = f.read()
                
                # Count transactions for progress estimation
                line_count = len([l for l in csv_content.split('\n') if l.strip()])
                
                # Show progress dialog
                progress = QProgressDialog("Importing and categorizing transactions...\nThis may take a few minutes for large files.", None, 0, 0, self)
                progress.setWindowModality(Qt.WindowModal)
                progress.setAutoClose(True)
                progress.show()
                
                result = self.client.import_bank_csv(csv_content, bank_format="generic")
                
                progress.close()
                
                self.show_info(f"Imported {result.get('imported', 0)} transactions")
                self.load_transactions()
                self.load_unknowns()
            except Exception as e:
                if 'progress' in locals():
                    progress.close()
                self.show_error(f"Failed to import/read CSV: {e}")

    # ============ UTILITY METHODS ============

    def show_error(self, message: str):
        """Show error message."""
        QMessageBox.critical(self, "Error", message)
        """Import transactions from image or PDF."""
        from PySide6.QtWidgets import QFileDialog, QProgressDialog
        from PySide6.QtCore import Qt
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image or PDF",
            "",
            "Images and PDFs (*.png *.jpg *.jpeg *.pdf *.bmp *.tiff)"
        )
        
        if file_path:
            # Show progress dialog
            progress = QProgressDialog("🤖 AI is analyzing your image...\nThis may take 10-30 seconds...", None, 0, 0, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setAutoClose(False)
            progress.show()
            
            try:
                # Process image (this may take a while)
                result = self.client.import_image(file_path)
                
                progress.close()
                
                # Build result message
                doc_type = result.get("document_type", "unknown")
                confidence = result.get("confidence", 0)
                imported = result.get("imported", 0)
                duplicates = result.get("duplicates_found", 0)
                warnings = result.get("warnings", [])
                
                message = f"Document Type: {doc_type.replace('_', ' ').title()}\n"
                message += f"Confidence: {confidence:.0%}\n\n"
                message += f"Imported: {imported} transaction(s)\n"
                
                if duplicates > 0:
                    message += f"Duplicates Skipped: {duplicates}\n"
                
                if warnings:
                    message += "\nWarnings:\n"
                    for warning in warnings:
                        message += f"• {warning}\n"
                
                self.import_status.setText(message)
                
                if imported > 0:
                    self.show_info(f"Successfully imported {imported} transaction(s) from {doc_type.replace('_', ' ')}")
                    self.load_transactions()
                    self.load_unknowns()
                elif duplicates > 0:
                    self.show_info(f"No new transactions imported - {duplicates} duplicates found")
                else:
                    self.show_info("Document processed but no transactions imported")
                
            except Exception as e:
                progress.close()
                self.import_status.setText(f"Error: {str(e)}")
                self.show_error(f"Failed to process image: {e}")

    def import_text(self):
        """Import transactions from pasted text using AI."""
        from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QPushButton, QDialog
        
        # Create dialog with text area
        dialog = QDialog(self)
        dialog.setWindowTitle("Paste Transaction Text")
        dialog.setGeometry(100, 100, 600, 400)
        
        layout = QVBoxLayout()
        
        label = QLabel("Paste text from your bank statement or receipt:")
        layout.addWidget(label)
        
        text_edit = QTextEdit()
        text_edit.setPlaceholderText(
            "Example:\n"
            "12/14/2025  McDonald's  $12.50\n"
            "12/14/2025  Petrol Station  R45.00\n"
            "12/15/2025  Grocery Store  $87.32"
        )
        layout.addWidget(text_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec() == QDialog.Accepted:
            text = text_edit.toPlainText().strip()
            
            if not text:
                self.show_error("Please paste some text")
                return
            
            # Show loading animation
            from PySide6.QtWidgets import QProgressDialog
            from PySide6.QtCore import Qt
            progress = QProgressDialog("🤖 AI is parsing your text...\nThis may take a few seconds...", None, 0, 0, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setAutoClose(True)
            progress.show()
            
            try:
                # Send to AI for parsing
                result = self.client.import_text(text)
                progress.close()
                
                # Build result message
                doc_type = result.get("document_type", "unknown")
                confidence = result.get("confidence", 0)
                imported = result.get("imported", 0)
                duplicates = result.get("duplicates_found", 0)
                warnings = result.get("warnings", [])
                
                message = f"AI detected: {doc_type.replace('_', ' ').title()}\n"
                message += f"Confidence: {confidence:.0%}\n\n"
                message += f"Imported: {imported} transaction(s)\n"
                
                if duplicates > 0:
                    message += f"Duplicates Skipped: {duplicates}\n"
                
                if warnings:
                    message += "\nWarnings:\n"
                    for warning in warnings:
                        message += f"• {warning}\n"
                
                self.import_status.setText(message)
                
                if imported > 0:
                    self.show_info(f"✅ Imported {imported} transaction(s)!\n\nTransactions have been automatically categorized by AI.\nCheck 'Unknowns' tab if any couldn't be categorized.")
                    self.load_transactions()
                    self.load_unknowns()
                elif duplicates > 0:
                    self.show_info(f"No new transactions - {duplicates} duplicates found")
                else:
                    self.show_info("No transactions found. Try adjusting the text format.")
                
            except Exception as e:
                progress.close()
                self.import_status.setText(f"Error: {str(e)}")
                self.show_error(f"Failed to parse text: {e}")

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
    
    def pie_chart_clicked(self, event):
        """Handle pie chart click to drill down into subcategories."""
        if not hasattr(self, '_pie_slice_data') or not self._pie_slice_data:
            print("No pie slice data available")
            return
            
        # Get click position
        pos = event.position().toPoint()
        x = pos.x()
        y = pos.y()
        
        # Get label size
        label_width = self.category_chart_label.width()
        label_height = self.category_chart_label.height()
        
        # Calculate center
        center_x = label_width / 2
        center_y = label_height / 2
        
        # Calculate relative position from center (-1 to 1)
        rel_x = (x - center_x) / (min(label_width, label_height) / 2.2)
        rel_y = (center_y - y) / (min(label_width, label_height) / 2.2)  # Flip Y
        
        # Calculate distance from center
        import math
        distance = math.sqrt(rel_x**2 + rel_y**2)
        
        print(f"Click: x={x}, y={y}, rel_x={rel_x:.2f}, rel_y={rel_y:.2f}, distance={distance:.2f}")
        
        # Check if click is within pie radius (0.05 to 1.2 for very forgiving detection)
        if distance < 0.05 or distance > 1.2:
            print("Click outside pie chart area")
            return
        
        # Calculate angle (0-360, starting from right, counter-clockwise)
        angle = math.atan2(rel_y, rel_x) * 180 / math.pi
        if angle < 0:
            angle += 360
        
        # Matplotlib pies start at 90\u00b0 (top) and go counter-clockwise
        # Adjust angle to match matplotlib's coordinate system
        adjusted_angle = (90 - angle) % 360
        
        print(f"Angle: {angle:.1f}\u00b0, Adjusted: {adjusted_angle:.1f}\u00b0")
        
        # Calculate which slice based on cumulative angles
        total = sum(size for _, size in self._pie_slice_data)
        cumulative = 0
        
        for i, (category, size) in enumerate(self._pie_slice_data):
            percentage = (size / total) * 360
            print(f"Slice {i}: {category}, range={cumulative:.1f}° to {cumulative + percentage:.1f}°")
            # Add 15 degree tolerance for much easier clicking
            if (cumulative - 15) <= adjusted_angle < (cumulative + percentage + 15):
                print(f"✓ Clicked on: {category}")
                self.drill_down_category(category)
                return
            cumulative += percentage
        
        print("No slice matched")
    
    def drill_down_category(self, category: str):
        """Drill down into a category to show subcategories."""
        # Check if this category has subcategories
        has_children = any(
            cat.get('parent_id') and 
            any(c.get('id') == cat.get('parent_id') and c.get('name') == category 
                for c in self.categories_list)
            for cat in self.categories_list
        )
        
        # Also check for path-based subcategories
        has_path_children = any(
            (cat.get('category_path') or '').startswith(category + '/')
            for cat in self.transactions
        )
        
        if has_children or has_path_children or '/' not in category:
            print(f"Drilling down into: {category}")
            self.chart_drill_down_stack.append(category)
            self.update_dashboard()
        else:
            print(f"No subcategories found for: {category}")
    
    def pie_chart_back(self):
        """Go back to previous drill-down level."""
        if self.chart_drill_down_stack:
            self.chart_drill_down_stack.pop()
            if not self.chart_drill_down_stack:
                self.chart_back_btn.setVisible(False)
            self.update_dashboard()

    def update_dashboard(self):
        """Update dashboard charts and statistics."""
        try:
            import matplotlib
            matplotlib.use('Agg')  # Use non-interactive backend
            import matplotlib.pyplot as plt
            from io import BytesIO
            from PySide6.QtGui import QPixmap
            from datetime import datetime, timedelta
            from collections import defaultdict
            
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
                self._pie_slice_data = sorted_cats
                
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
            if self.budgets:
                budget_names = []
                budget_limits = []
                budget_spent = []
                
                print(f"\n=== BUDGET CHART DEBUG ===")
                print(f"Number of budgets: {len(self.budgets)}")
                
                for budget in self.budgets[:6]:  # Top 6 budgets
                    cat = budget.get('category_path', 'All')
                    budget_names.append(cat if cat else 'All')
                    amount = budget.get('amount', 0)
                    budget_limits.append(amount)
                    
                    print(f"Budget: {cat}, Amount: {amount}")
                    
                    # Calculate spent
                    filtered = [t for t in self.transactions 
                               if t.get('transaction_type') == 'expense']
                    if cat and cat != 'All':
                        filtered = [t for t in filtered 
                                   if (t.get('category_path') or '').startswith(cat)]
                    spent = sum(t.get('amount', 0) for t in filtered)
                    budget_spent.append(spent)
                    print(f"  Spent: {spent}")
                
                print(f"Budget limits: {budget_limits}")
                print(f"Budget spent: {budget_spent}")
                
                fig, ax = plt.subplots(figsize=(7, 5.5), facecolor='white')
                fig.patch.set_facecolor('white')
                ax.set_facecolor('#fafbff')
                x = range(len(budget_names))
                width = 0.35
                
                # Use color palette for budget vs spent bars
                bars1 = ax.bar([i - width/2 for i in x], budget_limits, width, label='Budget', 
                              color=COLOR_PALETTE['primary'], alpha=0.8, edgecolor=COLOR_PALETTE['primary_dark'], linewidth=1.5)
                bars2 = ax.bar([i + width/2 for i in x], budget_spent, width, label='Spent', 
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
                import matplotlib.colors as mcolors
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
            print(f"Error updating dashboard: {e}")
            import traceback
            traceback.print_exc()


def main():
    app = QApplication(sys.argv)
    window = BudgetAppMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

