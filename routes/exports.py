"""
Export Routes - CSV and PDF download endpoints
"""
import logging
from datetime import datetime
from functools import wraps

from flask import Blueprint, Response, flash, redirect, request, session, url_for

from services.export_service import ExportService

logger = logging.getLogger(__name__)

exports_bp = Blueprint('exports', __name__)


def login_required(f):
    """Decorator to require login for export routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Bu sayfaya erişmek için giriş yapmalısınız.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def log_export(export_type: str, format_type: str, user_id: str):
    """Log export activity"""
    logger.info(f"Export: user={user_id}, type={export_type}, format={format_type}")


# ==================
# APPOINTMENTS EXPORT
# ==================

@exports_bp.route('/appointments/csv')
@login_required
def appointments_csv():
    """Export appointments as CSV"""
    user_id = str(session.get('user_id'))
    
    # Get filters from query params
    status_filter = request.args.get('status')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    try:
        export_service = ExportService(user_id)
        csv_content = export_service.generate_appointments_csv(
            status_filter=status_filter,
            date_from=date_from,
            date_to=date_to
        )
        
        log_export('appointments', 'csv', user_id)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'randevular_{timestamp}.csv'
        
        return Response(
            csv_content,
            mimetype='text/csv; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': 'text/csv; charset=utf-8'
            }
        )
    except Exception as e:
        logger.error(f"Appointments CSV export error: {str(e)}")
        flash('CSV oluşturulurken bir hata oluştu.', 'error')
        return redirect(url_for('dashboard.appointments'))


@exports_bp.route('/appointments/pdf')
@login_required
def appointments_pdf():
    """Export appointments as PDF"""
    user_id = str(session.get('user_id'))
    
    # Get filters from query params
    status_filter = request.args.get('status')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    try:
        export_service = ExportService(user_id)
        pdf_content = export_service.generate_appointments_pdf(
            status_filter=status_filter,
            date_from=date_from,
            date_to=date_to
        )
        
        log_export('appointments', 'pdf', user_id)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'randevular_{timestamp}.pdf'
        
        return Response(
            pdf_content,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': 'application/pdf'
            }
        )
    except Exception as e:
        logger.error(f"Appointments PDF export error: {str(e)}")
        flash('PDF oluşturulurken bir hata oluştu.', 'error')
        return redirect(url_for('dashboard.appointments'))


# ==================
# CUSTOMERS EXPORT
# ==================

@exports_bp.route('/customers/csv')
@login_required
def customers_csv():
    """Export customers as CSV"""
    user_id = str(session.get('user_id'))
    
    try:
        export_service = ExportService(user_id)
        csv_content = export_service.generate_customers_csv()
        
        log_export('customers', 'csv', user_id)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'musteriler_{timestamp}.csv'
        
        return Response(
            csv_content,
            mimetype='text/csv; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': 'text/csv; charset=utf-8'
            }
        )
    except Exception as e:
        logger.error(f"Customers CSV export error: {str(e)}")
        flash('CSV oluşturulurken bir hata oluştu.', 'error')
        return redirect(url_for('dashboard.stats'))


@exports_bp.route('/customers/pdf')
@login_required
def customers_pdf():
    """Export customers as PDF"""
    user_id = str(session.get('user_id'))
    
    try:
        export_service = ExportService(user_id)
        pdf_content = export_service.generate_customers_pdf()
        
        log_export('customers', 'pdf', user_id)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'musteriler_{timestamp}.pdf'
        
        return Response(
            pdf_content,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': 'application/pdf'
            }
        )
    except Exception as e:
        logger.error(f"Customers PDF export error: {str(e)}")
        flash('PDF oluşturulurken bir hata oluştu.', 'error')
        return redirect(url_for('dashboard.stats'))


# ==================
# FINANCIAL REPORT EXPORT
# ==================

@exports_bp.route('/financial/csv')
@login_required
def financial_csv():
    """Export financial report as CSV"""
    user_id = str(session.get('user_id'))
    
    try:
        months = request.args.get('months', 12, type=int)
        
        export_service = ExportService(user_id)
        csv_content = export_service.generate_financial_csv(months=months)
        
        log_export('financial', 'csv', user_id)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'finansal_rapor_{timestamp}.csv'
        
        return Response(
            csv_content,
            mimetype='text/csv; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': 'text/csv; charset=utf-8'
            }
        )
    except Exception as e:
        logger.error(f"Financial CSV export error: {str(e)}")
        flash('CSV oluşturulurken bir hata oluştu.', 'error')
        return redirect(url_for('dashboard.stats'))


@exports_bp.route('/financial/pdf')
@login_required
def financial_pdf():
    """Export financial report as PDF"""
    user_id = str(session.get('user_id'))
    
    try:
        months = request.args.get('months', 12, type=int)
        
        export_service = ExportService(user_id)
        pdf_content = export_service.generate_financial_pdf(months=months)
        
        log_export('financial', 'pdf', user_id)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'finansal_rapor_{timestamp}.pdf'
        
        return Response(
            pdf_content,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': 'application/pdf'
            }
        )
    except Exception as e:
        logger.error(f"Financial PDF export error: {str(e)}")
        flash('PDF oluşturulurken bir hata oluştu.', 'error')
        return redirect(url_for('dashboard.stats'))
