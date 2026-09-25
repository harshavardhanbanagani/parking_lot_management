import datetime
import math
from decimal import Decimal
from django.utils import timezone
from .models import Booking, BookingStatus, ParkingSlot, Pricing, VehicleType


def generate_booking_id():
    """Generate user-friendly sequential booking ID, e.g. PB20260001."""
    year = timezone.now().strftime('%Y')
    prefix = f"PB{year}"
    last_booking = Booking.objects.filter(booking_id__startswith=prefix).order_by('-id').first()
    if last_booking:
        try:
            last_seq = int(last_booking.booking_id.replace(prefix, ''))
            new_seq = last_seq + 1
        except ValueError:
            new_seq = Booking.objects.count() + 1
    else:
        new_seq = 1
    return f"{prefix}{new_seq:04d}"


def generate_transaction_id():
    """Generate user-friendly payment transaction ID, e.g. TXN202609230001."""
    date_str = timezone.now().strftime('%Y%m%d')
    prefix = f"TXN{date_str}"
    from .models import Payment
    last_payment = Payment.objects.filter(transaction_id__startswith=prefix).order_by('-id').first()
    if last_payment:
        try:
            last_seq = int(last_payment.transaction_id.replace(prefix, ''))
            new_seq = last_seq + 1
        except ValueError:
            new_seq = Payment.objects.count() + 1
    else:
        new_seq = 1
    return f"{prefix}{new_seq:04d}"


def get_current_pricing(vehicle_type):
    """Get the current rate from the single Pricing table source of truth."""
    default_rate = Decimal('30.00') if vehicle_type == VehicleType.CAR else Decimal('15.00')
    pricing_obj = Pricing.objects.filter(vehicle_type=vehicle_type).first()
    if pricing_obj:
        return pricing_obj.price_per_hour
    return default_rate


def calculate_duration_and_amount(vehicle_type, start_time, end_time):
    """
    Calculate duration in hours and total cost based on the configured rate in Pricing.
    """
    dummy_date = datetime.date(2000, 1, 1)
    dt_start = datetime.datetime.combine(dummy_date, start_time)
    dt_end = datetime.datetime.combine(dummy_date, end_time)
    
    diff_seconds = (dt_end - dt_start).total_seconds()
    if diff_seconds <= 0:
        duration_hours = Decimal('1.0')
    else:
        hours = diff_seconds / 3600.0
        duration_hours = Decimal(str(max(1.0, math.ceil(hours * 2) / 2)))

    rate = get_current_pricing(vehicle_type)
    total_amount = duration_hours * rate
    return duration_hours, rate, total_amount


def is_slot_available(slot, booking_date, start_time, end_time, exclude_booking_id=None):
    """
    Check if a parking slot is available for the specified date and time window.
    Rule: Overlaps when (new_start < existing_end AND new_end > existing_start)
    Only blocks if existing booking is CONFIRMED or ACTIVE.
    (PENDING_PAYMENT does not block the slot).
    """
    if not slot.is_active:
        return False

    overlapping_bookings = Booking.objects.filter(
        parking_slot=slot,
        booking_date=booking_date,
        status__in=[BookingStatus.CONFIRMED, BookingStatus.ACTIVE],
        start_time__lt=end_time,
        end_time__gt=start_time
    )

    if exclude_booking_id:
        overlapping_bookings = overlapping_bookings.exclude(booking_id=exclude_booking_id)

    return not overlapping_bookings.exists()


def is_vehicle_already_booked(vehicle_number, booking_date, start_time, end_time, exclude_booking_id=None):
    """
    Check if the same vehicle has an overlapping CONFIRMED or ACTIVE booking.
    Prevents duplicate bookings for the same vehicle in the same time window.
    """
    clean_vnum = vehicle_number.strip().upper()
    overlapping_vehicle_bookings = Booking.objects.filter(
        vehicle_number__iexact=clean_vnum,
        booking_date=booking_date,
        status__in=[BookingStatus.CONFIRMED, BookingStatus.ACTIVE],
        start_time__lt=end_time,
        end_time__gt=start_time
    )

    if exclude_booking_id:
        overlapping_vehicle_bookings = overlapping_vehicle_bookings.exclude(booking_id=exclude_booking_id)

    return overlapping_vehicle_bookings.exists()


def get_slot_status_for_window(slot, booking_date, start_time, end_time):
    """
    Return calculated display status for UI:
    - 'AVAILABLE' (Green)
    - 'OCCUPIED' (Gray - active parked)
    - 'BOOKED' (Red - confirmed reservation)
    """
    if not slot.is_active:
        return 'INACTIVE'

    active_booking = Booking.objects.filter(
        parking_slot=slot,
        booking_date=booking_date,
        status=BookingStatus.ACTIVE,
        start_time__lt=end_time,
        end_time__gt=start_time
    ).first()
    if active_booking:
        return 'OCCUPIED'

    confirmed_booking = Booking.objects.filter(
        parking_slot=slot,
        booking_date=booking_date,
        status=BookingStatus.CONFIRMED,
        start_time__lt=end_time,
        end_time__gt=start_time
    ).first()
    if confirmed_booking:
        return 'BOOKED'

    return 'AVAILABLE'
