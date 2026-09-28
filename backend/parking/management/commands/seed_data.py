import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from parking.models import (
    ParkingSlot, Pricing, Booking, Payment,
    VehicleType, BookingStatus, PaymentMethod, PaymentStatus
)


class Command(BaseCommand):
    help = 'Seeds initial parking slots, pricing, default admin user, and optional demo bookings.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--with-samples',
            action='store_true',
            help='Create sample/demo bookings and payments for testing.'
        )
        parser.add_argument(
            '--clear-bookings',
            action='store_true',
            help='Clear all existing booking and payment records.'
        )

    def handle(self, *args, **options):
        self.stdout.write("Starting database setup...")

        if options.get('clear_bookings'):
            b_cnt = Booking.objects.count()
            p_cnt = Payment.objects.count()
            Payment.objects.all().delete()
            Booking.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Cleared {b_cnt} bookings and {p_cnt} payments."))

        # 1. Create Default Admin User
        admin_user, created = User.objects.get_or_create(username='admin')
        if created:
            admin_user.set_password('admin123')
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.email = 'admin@parkease.local'
            admin_user.first_name = 'Parking'
            admin_user.last_name = 'Admin'
            admin_user.save()
            self.stdout.write(self.style.SUCCESS("Created Superuser: admin / admin123"))
        else:
            admin_user.set_password('admin123')
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.save()
            self.stdout.write("Admin user already exists. Password verified as admin123")

        # 2. Setup Centralized Pricing (Single source of truth)
        car_price, _ = Pricing.objects.get_or_create(
            vehicle_type=VehicleType.CAR,
            defaults={'price_per_hour': Decimal('30.00')}
        )
        bike_price, _ = Pricing.objects.get_or_create(
            vehicle_type=VehicleType.BIKE,
            defaults={'price_per_hour': Decimal('15.00')}
        )
        self.stdout.write(self.style.SUCCESS("Configured default pricing: Car Rs.30/hr, Bike Rs.15/hr"))

        # 3. Create Parking Slots: 10 Cars (A01-A10), 10 Bikes (B01-B10)
        car_slots = []
        for i in range(1, 11):
            slot_num = f"A{i:02d}"
            slot, _ = ParkingSlot.objects.get_or_create(
                slot_number=slot_num,
                defaults={
                    'vehicle_type': VehicleType.CAR,
                    'is_active': True
                }
            )
            car_slots.append(slot)

        bike_slots = []
        for i in range(1, 11):
            slot_num = f"B{i:02d}"
            slot, _ = ParkingSlot.objects.get_or_create(
                slot_number=slot_num,
                defaults={
                    'vehicle_type': VehicleType.BIKE,
                    'is_active': True
                }
            )
            bike_slots.append(slot)

        self.stdout.write(self.style.SUCCESS("Verified 10 Car slots (A01-A10) and 10 Bike slots (B01-B10)."))

        # 4. Optional Sample Bookings
        if options.get('with_samples'):
            today = timezone.localdate()

            b1, c1 = Booking.objects.get_or_create(
                booking_id="PB20260001",
                defaults={
                    'customer_name': "Rahul Sharma",
                    'phone': "9876543210",
                    'email': "rahul.sharma@example.com",
                    'vehicle_number': "AP39AB1234",
                    'vehicle_type': VehicleType.CAR,
                    'parking_slot': car_slots[0],
                    'booking_date': today,
                    'start_time': datetime.time(9, 0),
                    'end_time': datetime.time(13, 0),
                    'amount': Decimal('120.00'),
                    'status': BookingStatus.ACTIVE,
                    'check_in_time': timezone.now() - datetime.timedelta(hours=1)
                }
            )
            if c1:
                Payment.objects.create(
                    transaction_id="TXN202609010001",
                    booking=b1,
                    amount=b1.amount,
                    payment_method=PaymentMethod.UPI,
                    payment_status=PaymentStatus.PAID
                )

            self.stdout.write(self.style.SUCCESS("Sample demo bookings created."))

        self.stdout.write(self.style.SUCCESS("Database setup completed successfully!"))
