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
    help = 'Seeds initial parking slots, pricing, default admin user, and demo bookings.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting database seeding...")

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

        self.stdout.write(self.style.SUCCESS("Created 10 Car slots (A01-A10) and 10 Bike slots (B01-B10)."))

        # 4. Create Sample Bookings for Demonstration
        today = timezone.localdate()

        # Sample 1: Active parked car in A01
        b1, c1 = Booking.objects.get_or_create(
            booking_id="PB20260001",
            defaults={
                'customer_name': "Rahul Sharma",
                'phone': "9876543210",
                'email': "rahul.sharma@example.com",
                'vehicle_number': "AP39AB1234",
                'vehicle_type': VehicleType.CAR,
                'parking_slot': car_slots[0], # A01
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

        # Sample 2: Confirmed booking in A02
        b2, c2 = Booking.objects.get_or_create(
            booking_id="PB20260002",
            defaults={
                'customer_name': "Priya Verma",
                'phone': "9812345678",
                'email': "priya@example.com",
                'vehicle_number': "DL01XY9876",
                'vehicle_type': VehicleType.CAR,
                'parking_slot': car_slots[1], # A02
                'booking_date': today,
                'start_time': datetime.time(14, 0),
                'end_time': datetime.time(17, 0),
                'amount': Decimal('90.00'),
                'status': BookingStatus.CONFIRMED
            }
        )
        if c2:
            Payment.objects.create(
                transaction_id="TXN202609010002",
                booking=b2,
                amount=b2.amount,
                payment_method=PaymentMethod.CARD,
                payment_status=PaymentStatus.PAID
            )

        # Sample 3: Completed bike booking in B01
        b3, c3 = Booking.objects.get_or_create(
            booking_id="PB20260003",
            defaults={
                'customer_name': "Harsha Vardhan",
                'phone': "9988776655",
                'email': "harsha@example.com",
                'vehicle_number': "KA03MN4567",
                'vehicle_type': VehicleType.BIKE,
                'parking_slot': bike_slots[0], # B01
                'booking_date': today,
                'start_time': datetime.time(8, 0),
                'end_time': datetime.time(10, 0),
                'amount': Decimal('30.00'),
                'status': BookingStatus.COMPLETED,
                'check_in_time': timezone.now() - datetime.timedelta(hours=4),
                'check_out_time': timezone.now() - datetime.timedelta(hours=2)
            }
        )
        if c3:
            Payment.objects.create(
                transaction_id="TXN202609010003",
                booking=b3,
                amount=b3.amount,
                payment_method=PaymentMethod.CASH,
                payment_status=PaymentStatus.PAID
            )

        self.stdout.write(self.style.SUCCESS("Database seeding completed successfully!"))
