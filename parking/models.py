from django.db import models
from django.utils import timezone


class VehicleType(models.TextChoices):
    CAR = 'CAR', 'Car'
    BIKE = 'BIKE', 'Bike'


class BookingStatus(models.TextChoices):
    PENDING_PAYMENT = 'PENDING_PAYMENT', 'Pending Payment'
    CONFIRMED = 'CONFIRMED', 'Confirmed'
    ACTIVE = 'ACTIVE', 'Active (Parked)'
    COMPLETED = 'COMPLETED', 'Completed'
    CANCELLED = 'CANCELLED', 'Cancelled'


class PaymentMethod(models.TextChoices):
    UPI = 'UPI', 'UPI'
    CARD = 'CARD', 'Credit / Debit Card'
    CASH = 'CASH', 'Cash at Counter'


class PaymentStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    PAID = 'PAID', 'Paid'


class Pricing(models.Model):
    """
    Single Source of Truth for hourly parking rates per vehicle type.
    """
    vehicle_type = models.CharField(
        max_length=10,
        choices=VehicleType.choices,
        unique=True
    )
    price_per_hour = models.DecimalField(max_digits=8, decimal_places=2)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Pricing Configuration'

    def __str__(self):
        return f"{self.get_vehicle_type_display()} - ₹{self.price_per_hour}/hour"


class ParkingSlot(models.Model):
    """
    Physical parking slot entity.
    Notice: No permanent status or rate stored here. Status is calculated dynamically from bookings.
    """
    slot_number = models.CharField(max_length=10, unique=True)
    vehicle_type = models.CharField(max_length=10, choices=VehicleType.choices, default=VehicleType.CAR)
    is_active = models.BooleanField(default=True, help_text="Designates whether this slot is operational")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['slot_number']

    def __str__(self):
        return f"Slot {self.slot_number} ({self.get_vehicle_type_display()})"


class Booking(models.Model):
    """Customer parking reservation."""
    booking_id = models.CharField(max_length=25, unique=True, db_index=True)
    customer_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True, null=True)
    vehicle_number = models.CharField(max_length=20, db_index=True)
    vehicle_type = models.CharField(max_length=10, choices=VehicleType.choices, default=VehicleType.CAR)
    parking_slot = models.ForeignKey(ParkingSlot, on_delete=models.CASCADE, related_name='bookings')
    booking_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING_PAYMENT,
        db_index=True
    )
    check_in_time = models.DateTimeField(null=True, blank=True)
    check_out_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-booking_date', '-start_time', '-created_at']

    def __str__(self):
        return f"{self.booking_id} - {self.parking_slot.slot_number} ({self.status})"

    @property
    def duration_hours(self):
        """Calculate duration in hours (minimum 1 hour)."""
        import datetime
        dt_start = datetime.datetime.combine(self.booking_date, self.start_time)
        dt_end = datetime.datetime.combine(self.booking_date, self.end_time)
        diff_seconds = (dt_end - dt_start).total_seconds()
        hours = diff_seconds / 3600.0
        return max(1.0, round(hours, 1))

    def can_be_cancelled(self):
        """Can be cancelled if status is CONFIRMED and booking start datetime is in the future."""
        import datetime
        if self.status != BookingStatus.CONFIRMED:
            return False
        
        now = timezone.localtime(timezone.now())
        booking_start_dt = timezone.make_aware(
            datetime.datetime.combine(self.booking_date, self.start_time)
        )
        return now < booking_start_dt


class Payment(models.Model):
    """Payment record linked to a reservation."""
    transaction_id = models.CharField(max_length=35, unique=True, db_index=True)
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    payment_method = models.CharField(max_length=15, choices=PaymentMethod.choices, default=PaymentMethod.UPI)
    payment_status = models.CharField(max_length=15, choices=PaymentStatus.choices, default=PaymentStatus.PAID)
    payment_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_id} - {self.booking.booking_id} (₹{self.amount})"
