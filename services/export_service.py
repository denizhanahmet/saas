"""
Export Service - CSV and PDF generation for appointments, customers, and financial reports
"""
import csv
import io
import logging
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from firebase_realtime import get_data

logger = logging.getLogger(__name__)


class ExportService:
    """Service for generating CSV and PDF exports"""
    
    def __init__(self, user_id: str):
        self.user_id = str(user_id)
        self.styles = getSampleStyleSheet()
        
    # ==================
    # APPOINTMENTS EXPORT
    # ==================
    
    def get_user_appointments(self, status_filter: str = None, 
                               date_from: str = None, date_to: str = None) -> List[Dict]:
        """Get appointments for the current user with optional filters"""
        all_appointments = get_data('appointments') or {}
        
        appointments = []
        for apt in all_appointments.values():
            if str(apt.get('user_id')) != self.user_id:
                continue
                
            # Status filter
            if status_filter and apt.get('status') != status_filter:
                continue
            
            # Date range filter
            apt_date_str = apt.get('appointment_date', '')
            if date_from:
                try:
                    if apt_date_str < date_from:
                        continue
                except:
                    pass
            if date_to:
                try:
                    if apt_date_str > date_to:
                        continue
                except:
                    pass
            
            appointments.append(apt)
        
        # Sort by date
        appointments.sort(key=lambda x: (x.get('appointment_date', ''), x.get('appointment_time', '')))
        return appointments
    
    def generate_appointments_csv(self, status_filter: str = None,
                                   date_from: str = None, date_to: str = None) -> str:
        """Generate CSV content for appointments"""
        appointments = self.get_user_appointments(status_filter, date_from, date_to)
        
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        
        # Header
        writer.writerow([
            'Tarih', 'Saat', 'Baslik', 'Musteri Adi', 'Musteri Telefon',
            'Musteri Email', 'Sure (dk)', 'Durum', 'Konum', 'Notlar'
        ])
        
        # Status mapping
        status_map = {
            'scheduled': 'Planlandi',
            'approved': 'Onaylandi',
            'pending': 'Bekliyor',
            'completed': 'Tamamlandi',
            'cancelled': 'Iptal',
            'rejected': 'Reddedildi'
        }
        
        for apt in appointments:
            writer.writerow([
                apt.get('appointment_date', ''),
                apt.get('appointment_time', ''),
                apt.get('title', ''),
                apt.get('client_name', ''),
                apt.get('client_phone', ''),
                apt.get('client_email', ''),
                apt.get('duration', 60),
                status_map.get(apt.get('status', ''), apt.get('status', '')),
                apt.get('location', ''),
                apt.get('notes', '')
            ])
        
        return output.getvalue()
    
    def generate_appointments_pdf(self, status_filter: str = None,
                                   date_from: str = None, date_to: str = None) -> bytes:
        """Generate PDF content for appointments"""
        appointments = self.get_user_appointments(status_filter, date_from, date_to)
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), 
                               leftMargin=1*cm, rightMargin=1*cm,
                               topMargin=1*cm, bottomMargin=1*cm)
        
        elements = []
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            spaceAfter=20,
            alignment=1  # Center
        )
        elements.append(Paragraph('Randevu Listesi', title_style))
        
        # Date info
        date_style = ParagraphStyle(
            'DateInfo',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=20,
            alignment=1
        )
        elements.append(Paragraph(f'Olusturulma Tarihi: {datetime.now().strftime("%d.%m.%Y %H:%M")}', date_style))
        
        if not appointments:
            elements.append(Paragraph('Gosterilecek randevu bulunamadi.', self.styles['Normal']))
        else:
            # Table data
            status_map = {
                'scheduled': 'Planlandi',
                'approved': 'Onaylandi', 
                'pending': 'Bekliyor',
                'completed': 'Tamamlandi',
                'cancelled': 'Iptal',
                'rejected': 'Reddedildi'
            }
            
            data = [['Tarih', 'Saat', 'Baslik', 'Musteri', 'Telefon', 'Durum']]
            
            for apt in appointments:
                data.append([
                    apt.get('appointment_date', ''),
                    apt.get('appointment_time', ''),
                    apt.get('title', '')[:30],
                    apt.get('client_name', '')[:20],
                    apt.get('client_phone', ''),
                    status_map.get(apt.get('status', ''), apt.get('status', ''))
                ])
            
            # Create table
            col_widths = [2.5*cm, 1.8*cm, 5*cm, 4*cm, 3*cm, 2.5*cm]
            table = Table(data, colWidths=col_widths)
            
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3B82F6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
                ('ALTERNATINGROWCOLORS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F1F5F9')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            
            elements.append(table)
            
            # Summary
            elements.append(Spacer(1, 20))
            summary = f'Toplam: {len(appointments)} randevu'
            elements.append(Paragraph(summary, self.styles['Normal']))
        
        doc.build(elements)
        return buffer.getvalue()
    
    # ==================
    # CUSTOMERS EXPORT
    # ==================
    
    def get_unique_customers(self) -> List[Dict]:
        """Get unique customers from appointments"""
        all_appointments = get_data('appointments') or {}
        
        customers = {}
        for apt in all_appointments.values():
            if str(apt.get('user_id')) != self.user_id:
                continue
            
            # Use phone or email as unique key
            key = apt.get('client_phone') or apt.get('client_email') or apt.get('client_name')
            if not key:
                continue
                
            if key not in customers:
                customers[key] = {
                    'name': apt.get('client_name', ''),
                    'phone': apt.get('client_phone', ''),
                    'email': apt.get('client_email', ''),
                    'appointment_count': 0,
                    'last_appointment': apt.get('appointment_date', ''),
                    'first_appointment': apt.get('appointment_date', '')
                }
            
            customers[key]['appointment_count'] += 1
            
            # Update dates
            apt_date = apt.get('appointment_date', '')
            if apt_date > customers[key]['last_appointment']:
                customers[key]['last_appointment'] = apt_date
            if apt_date < customers[key]['first_appointment'] or not customers[key]['first_appointment']:
                customers[key]['first_appointment'] = apt_date
        
        return list(customers.values())
    
    def generate_customers_csv(self) -> str:
        """Generate CSV content for customers"""
        customers = self.get_unique_customers()
        
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        
        # Header
        writer.writerow([
            'Musteri Adi', 'Telefon', 'Email', 
            'Randevu Sayisi', 'Ilk Randevu', 'Son Randevu'
        ])
        
        for customer in customers:
            writer.writerow([
                customer.get('name', ''),
                customer.get('phone', ''),
                customer.get('email', ''),
                customer.get('appointment_count', 0),
                customer.get('first_appointment', ''),
                customer.get('last_appointment', '')
            ])
        
        return output.getvalue()
    
    def generate_customers_pdf(self) -> bytes:
        """Generate PDF content for customers"""
        customers = self.get_unique_customers()
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                               leftMargin=1.5*cm, rightMargin=1.5*cm,
                               topMargin=1.5*cm, bottomMargin=1.5*cm)
        
        elements = []
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            spaceAfter=20,
            alignment=1
        )
        elements.append(Paragraph('Musteri Listesi', title_style))
        
        # Date info
        date_style = ParagraphStyle(
            'DateInfo',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=20,
            alignment=1
        )
        elements.append(Paragraph(f'Olusturulma Tarihi: {datetime.now().strftime("%d.%m.%Y %H:%M")}', date_style))
        
        if not customers:
            elements.append(Paragraph('Gosterilecek musteri bulunamadi.', self.styles['Normal']))
        else:
            data = [['Ad Soyad', 'Telefon', 'Email', 'Randevu']]
            
            for customer in customers:
                data.append([
                    customer.get('name', '')[:25],
                    customer.get('phone', ''),
                    customer.get('email', '')[:25],
                    str(customer.get('appointment_count', 0))
                ])
            
            col_widths = [5*cm, 3.5*cm, 5*cm, 2*cm]
            table = Table(data, colWidths=col_widths)
            
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10B981')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            
            elements.append(table)
            
            elements.append(Spacer(1, 20))
            summary = f'Toplam: {len(customers)} musteri'
            elements.append(Paragraph(summary, self.styles['Normal']))
        
        doc.build(elements)
        return buffer.getvalue()
    
    # ==================
    # FINANCIAL REPORT
    # ==================
    
    def get_financial_data(self, months: int = 12) -> Dict:
        """Get financial/statistical data for reports"""
        all_appointments = get_data('appointments') or {}
        
        # Filter user's appointments
        user_appointments = [
            apt for apt in all_appointments.values()
            if str(apt.get('user_id')) == self.user_id
        ]
        
        # Monthly stats
        today = date.today()
        monthly_data = {}
        
        for i in range(months):
            month = today.month - i
            year = today.year
            while month <= 0:
                month += 12
                year -= 1
            
            key = f'{year}-{month:02d}'
            monthly_data[key] = {
                'year': year,
                'month': month,
                'total': 0,
                'completed': 0,
                'cancelled': 0,
                'pending': 0
            }
        
        # Count appointments
        for apt in user_appointments:
            apt_date = apt.get('appointment_date', '')
            if not apt_date:
                continue
            
            try:
                key = apt_date[:7]  # YYYY-MM
                if key in monthly_data:
                    monthly_data[key]['total'] += 1
                    status = apt.get('status', '')
                    if status == 'completed':
                        monthly_data[key]['completed'] += 1
                    elif status in ['cancelled', 'rejected']:
                        monthly_data[key]['cancelled'] += 1
                    elif status == 'pending':
                        monthly_data[key]['pending'] += 1
            except:
                continue
        
        # Overall stats
        total = len(user_appointments)
        completed = sum(1 for a in user_appointments if a.get('status') == 'completed')
        cancelled = sum(1 for a in user_appointments if a.get('status') in ['cancelled', 'rejected'])
        
        return {
            'monthly': monthly_data,
            'total_appointments': total,
            'total_completed': completed,
            'total_cancelled': cancelled,
            'completion_rate': round(completed / total * 100, 1) if total > 0 else 0
        }
    
    def generate_financial_csv(self, months: int = 12) -> str:
        """Generate CSV content for financial report"""
        data = self.get_financial_data(months)
        
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        
        # Header
        writer.writerow(['FINANSAL RAPOR'])
        writer.writerow([f'Olusturulma: {datetime.now().strftime("%d.%m.%Y %H:%M")}'])
        writer.writerow([])
        
        # Summary
        writer.writerow(['OZET'])
        writer.writerow(['Toplam Randevu', data['total_appointments']])
        writer.writerow(['Tamamlanan', data['total_completed']])
        writer.writerow(['Iptal Edilen', data['total_cancelled']])
        writer.writerow(['Basari Orani (%)', data['completion_rate']])
        writer.writerow([])
        
        # Monthly breakdown
        writer.writerow(['AYLIK DAGILIM'])
        writer.writerow(['Yil-Ay', 'Toplam', 'Tamamlanan', 'Iptal', 'Bekleyen'])
        
        month_names = ['', 'Oca', 'Sub', 'Mar', 'Nis', 'May', 'Haz', 
                       'Tem', 'Agu', 'Eyl', 'Eki', 'Kas', 'Ara']
        
        for key in sorted(data['monthly'].keys(), reverse=True):
            m = data['monthly'][key]
            month_name = f"{month_names[m['month']]} {m['year']}"
            writer.writerow([
                month_name,
                m['total'],
                m['completed'],
                m['cancelled'],
                m['pending']
            ])
        
        return output.getvalue()
    
    def generate_financial_pdf(self, months: int = 12) -> bytes:
        """Generate PDF content for financial report"""
        data = self.get_financial_data(months)
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                               leftMargin=2*cm, rightMargin=2*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
        
        elements = []
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=20,
            spaceAfter=10,
            alignment=1
        )
        elements.append(Paragraph('Finansal Rapor', title_style))
        
        # Date
        date_style = ParagraphStyle(
            'DateInfo',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=30,
            alignment=1
        )
        elements.append(Paragraph(f'Olusturulma: {datetime.now().strftime("%d.%m.%Y %H:%M")}', date_style))
        
        # Summary section
        section_style = ParagraphStyle(
            'SectionTitle',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=10,
            textColor=colors.HexColor('#3B82F6')
        )
        elements.append(Paragraph('Genel Ozet', section_style))
        
        summary_data = [
            ['Metrik', 'Deger'],
            ['Toplam Randevu', str(data['total_appointments'])],
            ['Tamamlanan', str(data['total_completed'])],
            ['Iptal Edilen', str(data['total_cancelled'])],
            ['Basari Orani', f"%{data['completion_rate']}"]
        ]
        
        summary_table = Table(summary_data, colWidths=[8*cm, 4*cm])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8B5CF6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(summary_table)
        
        elements.append(Spacer(1, 30))
        
        # Monthly breakdown
        elements.append(Paragraph('Aylik Dagilim', section_style))
        
        month_names = ['', 'Oca', 'Sub', 'Mar', 'Nis', 'May', 'Haz', 
                       'Tem', 'Agu', 'Eyl', 'Eki', 'Kas', 'Ara']
        
        monthly_data = [['Ay', 'Toplam', 'Tamamlanan', 'Iptal', 'Bekleyen']]
        
        for key in sorted(data['monthly'].keys(), reverse=True):
            m = data['monthly'][key]
            month_name = f"{month_names[m['month']]} {m['year']}"
            monthly_data.append([
                month_name,
                str(m['total']),
                str(m['completed']),
                str(m['cancelled']),
                str(m['pending'])
            ])
        
        col_widths = [3*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm]
        monthly_table = Table(monthly_data, colWidths=col_widths)
        monthly_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10B981')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(monthly_table)
        
        doc.build(elements)
        return buffer.getvalue()
