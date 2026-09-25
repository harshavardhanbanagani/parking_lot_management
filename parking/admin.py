from django.contrib import admin
from .models import ParkingSlot, Booking, Payment, Pricing


@admin.register(Pricing)
class PricingAdmin(admin.ModelAdmin):
    list_display = ('vehicle_type', 'price_per_hour', 'updated_at')


@admin.register(ParkingSlot)
class ParkingSlotAdmin(admin.ModelAdmin):
    list_display = ('slot_number', 'vehicle_type', 'is_active', 'created_at')
    list_filter = ('vehicle_type', 'is_active')
    search_fields = ('slot_number',)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'booking_id', 'customer_name', 'phone', 'vehicle_number',
        'vehicle_type', 'parking_slot', 'booking_date', 'start_time',
        'end_time', 'amount', 'status', 'created_at'
    )
    list_filter = ('status', 'vehicle_type', 'booking_date')
    search_fields = ('booking_id', 'customer_name', 'phone', 'vehicle_number', 'parking_slot__slot_number')
    readonly_fields = ('booking_id', 'created_at')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'booking', 'amount', 'payment_method', 'payment_status', 'payment_date')
    list_filter = ('payment_method', 'payment_status')
    search_fields = ('transaction_id', 'booking__booking_id', 'booking__customer_name')
    readonly_fields = ('transaction_id', 'payment_date')
