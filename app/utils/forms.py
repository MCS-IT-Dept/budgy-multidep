from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, MultipleFileField
from wtforms import (
    StringField,
    TextAreaField,
    DecimalField,
    DateField,
    SelectField,
    IntegerField,
    HiddenField,
)
from wtforms.validators import DataRequired, Optional, NumberRange, Length, ValidationError

from app.models.purchase import Purchase


class PurchaseForm(FlaskForm):
    vendor_name = StringField(
        "Vendor Name", validators=[DataRequired(), Length(max=255)]
    )
    purchase_date = DateField("Purchase Date", validators=[DataRequired()])
    amount = DecimalField(
        "Amount ($)",
        validators=[DataRequired(), NumberRange(min=0.01, message="Amount must be positive")],
        places=2,
    )
    budget_line_item_id = SelectField(
        "Budget Line Item", coerce=int, validators=[DataRequired()]
    )
    custom_account_code = StringField(
        "Custom Account Code", validators=[Optional(), Length(max=100)]
    )
    custom_account_description = StringField(
        "Custom Account Description", validators=[Optional(), Length(max=255)]
    )
    description = TextAreaField("Description", validators=[Optional(), Length(max=2000)])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=2000)])
    po_number = StringField("PO Number", validators=[Optional(), Length(max=100)])
    invoice_number = StringField(
        "Invoice Number", validators=[Optional(), Length(max=100)]
    )
    payment_method = SelectField(
        "Payment Method",
        choices=[("", "— Select —")],
        validators=[Optional()],
    )
    attachments = MultipleFileField(
        "Receipt/Invoice Files",
        validators=[
            FileAllowed(["pdf", "jpg", "jpeg", "png"], "Only PDF, JPG, and PNG files are allowed.")
        ],
    )


class PurchaseStatusForm(FlaskForm):
    status = SelectField(
        "Status",
        choices=[(s, s.title()) for s in Purchase.STATUSES],
        validators=[DataRequired()],
    )
    review_notes = TextAreaField("Review Notes", validators=[Optional(), Length(max=2000)])


class BudgetAllocationForm(FlaskForm):
    fiscal_year_id = SelectField("Fiscal Year", coerce=int, validators=[DataRequired()])
    budget_line_item_id = SelectField(
        "Budget Line Item", coerce=int, validators=[DataRequired()]
    )
    allocated_amount = DecimalField(
        "Allocated Amount ($)",
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
    )


class FiscalYearForm(FlaskForm):
    label = StringField(
        "Label (e.g. 2025-2026)", validators=[DataRequired(), Length(max=20)]
    )
    start_date = DateField("Start Date", validators=[DataRequired()])
    end_date = DateField("End Date", validators=[DataRequired()])


class BudgetLineItemForm(FlaskForm):
    code = StringField("Code", validators=[DataRequired(), Length(max=50)])
    name = StringField("Name", validators=[DataRequired(), Length(max=255)])


class UserEditForm(FlaskForm):
    display_name = StringField(
        "Display Name", validators=[DataRequired(), Length(max=255)]
    )
    role = SelectField(
        "Role",
        choices=[("user", "User"), ("dept_admin", "Dept Admin"), ("global_admin", "Global Admin")],
        validators=[DataRequired()],
    )
    department_id = SelectField(
        "Department",
        coerce=int,
        validators=[Optional()],
    )
    is_active = SelectField(
        "Active",
        choices=[("1", "Yes"), ("0", "No")],
        validators=[DataRequired()],
    )


class DepartmentForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=255)])
    slug = StringField("Slug (URL-friendly)", validators=[DataRequired(), Length(max=100)])


class PaymentMethodForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=100)])
    sort_order = IntegerField("Sort Order", validators=[Optional()], default=0)


class BrandingForm(FlaskForm):
    organization_name = StringField(
        "Organization Name", validators=[Optional(), Length(max=255)]
    )
    logo = FileField(
        "Organization Logo",
        validators=[
            FileAllowed(["jpg", "jpeg", "png", "svg", "gif"], "Only image files are allowed.")
        ],
    )
