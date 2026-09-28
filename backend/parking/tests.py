import datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone

from .models import (
    ParkingSlot, Pricing, Booking, Payment,
    VehicleType, BookingStatus, PaymentMethod, PaymentStatus
)
from .utils import (
    is_slot_available, is_vehicle_already_booked,
    calculate_duration_and_amount,
    generate_booking_id, generate_transaction_id,
    get_slot_status_for_window
)
from .forms import (
    AvailabilitySearchForm, CustomerDetailsForm,
    CheckBookingForm, ParkingSlotForm, PricingForm
)


class ParkingSystemQATests(TestCase):
    """
    Professional Quality Assurance Test Suite.
    Validates end-to-end functionality, boundary conditions, edge cases,
    data integrity, security, and lifecycle transitions.
    """

    def setUp(self):
        self.client = Client()

        # 1. Staff Admin User
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@parkease.local',
            password='adminpassword123'
        )

        # 2. Pricing Single Source of Truth
        self.car_pricing = Pricing.objects.create(
            vehicle_type=VehicleType.CAR,
            price_per_hour=Decimal('30.00')
        )
        self.bike_pricing = Pricing.objects.create(
            vehicle_type=VehicleType.BIKE,
            price_per_hour=Decimal('15.00')
        )

        # 3. Parking Bays
        self.car_slot_1 = ParkingSlot.objects.create(
            slot_number='A01',
            vehicle_type=VehicleType.CAR
        )
        self.car_slot_2 = ParkingSlot.objects.create(
            slot_number='A02',
            vehicle_type=VehicleType.CAR
        )
        self.bike_slot_1 = ParkingSlot.objects.create(
            slot_number='B01',
            vehicle_type=VehicleType.BIKE
        )

        self.future_date = timezone.localdate() + datetime.timedelta(days=2)

    def test_01_pricing_and_duration_calculation(self):
        """Test duration calculation, half-hour rounding, and price computation."""
        start = datetime.time(10, 0)
        end = datetime.time(12, 0)  # 2 hours
        duration, rate, total = calculate_duration_and_amount(VehicleType.CAR, start, end)
        self.assertEqual(duration, Decimal('2.0'))
        self.assertEqual(rate, Decimal('30.00'))
        self.assertEqual(total, Decimal('60.00'))

        # Bike rate check
        duration_b, rate_b, total_b = calculate_duration_and_amount(VehicleType.BIKE, start, end)
        self.assertEqual(rate_b, Decimal('15.00'))
        self.assertEqual(total_b, Decimal('30.00'))

        # Minimum 1 hour fee check
        start_short = datetime.time(10, 0)
        end_short = datetime.time(10, 15)  # 15 mins -> charged min 1 hour
        duration_s, _, total_s = calculate_duration_and_amount(VehicleType.CAR, start_short, end_short)
        self.assertEqual(duration_s, Decimal('1.0'))
        self.assertEqual(total_s, Decimal('30.00'))

    def test_02_availability_search_form_validations(self):
        """Test search form validation for past dates, past times, and inverted times."""
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        
        # Negative test: Past date
        form_past = AvailabilitySearchForm(data={
            'booking_date': yesterday,
            'start_time': '10:00',
            'end_time': '12:00',
            'vehicle_type': 'CAR'
        })
        self.assertFalse(form_past.is_valid())
        self.assertIn('booking_date', form_past.errors)

        # Negative test: Inverted times
        form_time = AvailabilitySearchForm(data={
            'booking_date': self.future_date,
            'start_time': '14:00',
            'end_time': '12:00',
            'vehicle_type': 'CAR'
        })
        self.assertFalse(form_time.is_valid())
        self.assertIn('end_time', form_time.errors)

        # Positive test: Valid search parameters
        form_valid = AvailabilitySearchForm(data={
            'booking_date': self.future_date,
            'start_time': '10:00',
            'end_time': '12:00',
            'vehicle_type': 'CAR'
        })
        self.assertTrue(form_valid.is_valid())

    def test_03_time_overlap_exact_boundary_conditions(self):
        """
        Verify exact overlap boundary logic:
        Existing: 10:00 - 12:00
        - 08:00 - 10:00: OK (adjacent, no overlap)
        - 12:00 - 14:00: OK (adjacent, no overlap)
        - 10:30 - 11:30: COLLISION (subset)
        - 09:00 - 11:00: COLLISION (starts before, ends inside)
        - 11:00 - 13:00: COLLISION (starts inside, ends after)
        - 09:00 - 13:00: COLLISION (superset)
        """
        Booking.objects.create(
            booking_id='PB20260001',
            customer_name='Alice QA',
            phone='9876543210',
            vehicle_number='KA01AB1234',
            vehicle_type=VehicleType.CAR,
            parking_slot=self.car_slot_1,
            booking_date=self.future_date,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
            amount=Decimal('60.00'),
            status=BookingStatus.CONFIRMED
        )

        # Adjacent before: 08:00 - 10:00 -> TRUE
        self.assertTrue(is_slot_available(self.car_slot_1, self.future_date, datetime.time(8, 0), datetime.time(10, 0)))

        # Adjacent after: 12:00 - 14:00 -> TRUE
        self.assertTrue(is_slot_available(self.car_slot_1, self.future_date, datetime.time(12, 0), datetime.time(14, 0)))

        # Overlap inside: 10:30 - 11:30 -> FALSE
        self.assertFalse(is_slot_available(self.car_slot_1, self.future_date, datetime.time(10, 30), datetime.time(11, 30)))

        # Overlap early: 09:00 - 11:00 -> FALSE
        self.assertFalse(is_slot_available(self.car_slot_1, self.future_date, datetime.time(9, 0), datetime.time(11, 0)))

        # Overlap late: 11:00 - 13:00 -> FALSE
        self.assertFalse(is_slot_available(self.car_slot_1, self.future_date, datetime.time(11, 0), datetime.time(13, 0)))

        # Overlap engulf: 09:00 - 13:00 -> FALSE
        self.assertFalse(is_slot_available(self.car_slot_1, self.future_date, datetime.time(9, 0), datetime.time(13, 0)))

        # Another slot (Slot 2) should remain available
        self.assertTrue(is_slot_available(self.car_slot_2, self.future_date, datetime.time(10, 0), datetime.time(12, 0)))

    def test_04_vehicle_duplicate_booking_prevention(self):
        """Test that same vehicle plate cannot double-book different slots during same time."""
        vnum = 'DL01XYZ9999'
        Booking.objects.create(
            booking_id='PB20260002',
            customer_name='Bob Tester',
            phone='9123456789',
            vehicle_number=vnum,
            vehicle_type=VehicleType.CAR,
            parking_slot=self.car_slot_1,
            booking_date=self.future_date,
            start_time=datetime.time(14, 0),
            end_time=datetime.time(16, 0),
            amount=Decimal('60.00'),
            status=BookingStatus.CONFIRMED
        )

        # Same vehicle during overlapping time
        self.assertTrue(is_vehicle_already_booked(vnum, self.future_date, datetime.time(14, 30), datetime.time(15, 30)))
        # Different vehicle during same time
        self.assertFalse(is_vehicle_already_booked('KA05MM1111', self.future_date, datetime.time(14, 30), datetime.time(15, 30)))

    def test_05_sequential_id_generators(self):
        """Test sequential booking ID and transaction ID generation."""
        b1 = generate_booking_id()
        self.assertTrue(b1.startswith('PB'))
        
        t1 = generate_transaction_id()
        self.assertTrue(t1.startswith('TXN'))

    def test_06_complete_end_to_end_booking_flow(self):
        """
        Full End-to-End User Booking Journey:
        1. Search Availability
        2. Select Slot
        3. Enter Customer Details
        4. Review Summary
        5. Process Demo Payment (UPI)
        6. Receive Confirmation Pass
        """
        # 1. Search
        search_res = self.client.get(reverse('check_availability'), {
            'booking_date': str(self.future_date),
            'start_time': '16:00',
            'end_time': '18:00',
            'vehicle_type': 'CAR'
        })
        self.assertEqual(search_res.status_code, 200)

        # 2 & 3. Select Slot and Submit Customer Details
        details_res = self.client.post(reverse('select_slot', args=[self.car_slot_1.id]), {
            'customer_name': 'QA Tester Jane',
            'phone': '9876543210',
            'email': 'jane@example.com',
            'vehicle_number': 'MH02CD5678'
        })
        self.assertRedirects(details_res, reverse('booking_review'))

        # 4. Review
        review_res = self.client.get(reverse('booking_review'))
        self.assertEqual(review_res.status_code, 200)
        self.assertContains(review_res, 'MH02CD5678')

        # 5. Payment
        pay_res = self.client.post(reverse('payment'), {
            'payment_method': 'UPI'
        })
        
        booking = Booking.objects.get(vehicle_number='MH02CD5678')
        self.assertEqual(booking.status, BookingStatus.CONFIRMED)
        self.assertRedirects(pay_res, reverse('booking_confirmation', args=[booking.booking_id]))

        # 6. Confirmation Pass
        conf_res = self.client.get(reverse('booking_confirmation', args=[booking.booking_id]))
        self.assertEqual(conf_res.status_code, 200)
        self.assertContains(conf_res, booking.booking_id)
        self.assertContains(conf_res, 'ParkEase Pass')

    def test_07_cancellation_lifecycle_and_reopening(self):
        """Test customer self-service cancellation and immediate slot reopening."""
        booking = Booking.objects.create(
            booking_id='PB20260003',
            customer_name='Cancel Tester',
            phone='9998887776',
            vehicle_number='KA04EF4321',
            vehicle_type=VehicleType.CAR,
            parking_slot=self.car_slot_1,
            booking_date=self.future_date,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
            amount=Decimal('60.00'),
            status=BookingStatus.CONFIRMED
        )

        # Before cancellation: slot is blocked
        self.assertFalse(is_slot_available(self.car_slot_1, self.future_date, datetime.time(10, 0), datetime.time(12, 0)))

        # Cancel booking
        cancel_res = self.client.post(reverse('cancel_booking', args=[booking.booking_id]))
        self.assertEqual(cancel_res.status_code, 302)

        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingStatus.CANCELLED)

        # After cancellation: slot is immediately available
        self.assertTrue(is_slot_available(self.car_slot_1, self.future_date, datetime.time(10, 0), datetime.time(12, 0)))

    def test_08_check_booking_by_phone_number_only(self):
        """Test customer finding bookings using phone number alone without booking ID."""
        test_phone = '6300379942'
        
        Booking.objects.create(
            booking_id='PB20260010',
            customer_name='Phone Search User',
            phone=test_phone,
            vehicle_number='AP39AB1001',
            vehicle_type=VehicleType.CAR,
            parking_slot=self.car_slot_1,
            booking_date=self.future_date,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
            amount=Decimal('60.00'),
            status=BookingStatus.CONFIRMED
        )

        Booking.objects.create(
            booking_id='PB20260011',
            customer_name='Phone Search User',
            phone=test_phone,
            vehicle_number='AP39AB1002',
            vehicle_type=VehicleType.CAR,
            parking_slot=self.car_slot_2,
            booking_date=self.future_date + datetime.timedelta(days=1),
            start_time=datetime.time(14, 0),
            end_time=datetime.time(16, 0),
            amount=Decimal('60.00'),
            status=BookingStatus.CONFIRMED
        )

        res = self.client.get(reverse('check_booking'), {'phone': test_phone})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Found 2 Reservation(s)')
        self.assertContains(res, 'PB20260010')
        self.assertContains(res, 'PB20260011')

    def test_09_check_booking_by_booking_id_only(self):
        """Test lookup by booking ID alone."""
        b = Booking.objects.create(
            booking_id='PB20260099',
            customer_name='Single ID Search',
            phone='9876500000',
            vehicle_number='TS09AB9999',
            vehicle_type=VehicleType.CAR,
            parking_slot=self.car_slot_1,
            booking_date=self.future_date,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
            amount=Decimal('60.00'),
            status=BookingStatus.CONFIRMED
        )

        res = self.client.get(reverse('check_booking'), {'booking_id': 'pb20260099'})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'PB20260099')

    def test_10_admin_authentication_and_protection(self):
        """Ensure all admin views require staff authentication."""
        admin_urls = [
            'admin_dashboard',
            'admin_slots',
            'admin_pricing',
            'admin_bookings',
            'admin_customers',
            'admin_payments',
            'admin_reports',
        ]
        # Unauthenticated access should redirect to login
        for url_name in admin_urls:
            res = self.client.get(reverse(url_name))
            self.assertEqual(res.status_code, 302)
            self.assertIn(reverse('admin_login'), res.url)

        # Authenticate as staff admin
        self.client.login(username='admin', password='adminpassword123')
        for url_name in admin_urls:
            res = self.client.get(reverse(url_name))
            self.assertEqual(res.status_code, 200)

    def test_11_admin_slot_management_and_duplicate_prevention(self):
        """Test adding duplicate slots is cleanly prevented with validation error."""
        self.client.login(username='admin', password='adminpassword123')

        # Try to add duplicate slot A01
        form = ParkingSlotForm(data={
            'slot_number': 'A01',
            'vehicle_type': 'CAR',
            'is_active': True
        })
        self.assertFalse(form.is_valid())
        self.assertIn('slot_number', form.errors)

        # Add valid new slot C01
        form_valid = ParkingSlotForm(data={
            'slot_number': 'C01',
            'vehicle_type': 'CAR',
            'is_active': True
        })
        self.assertTrue(form_valid.is_valid())
        slot_c = form_valid.save()
        self.assertEqual(slot_c.slot_number, 'C01')

    def test_12_admin_pricing_positive_validation(self):
        """Test admin pricing rate updates reject zero or negative numbers."""
        self.client.login(username='admin', password='adminpassword123')

        # Negative price update
        res_neg = self.client.post(reverse('admin_pricing'), {
            'car_rate': '-10.00',
            'bike_rate': '0.00'
        })
        self.assertEqual(res_neg.status_code, 302)
        
        # Ensure rates did not change
        self.car_pricing.refresh_from_db()
        self.assertEqual(self.car_pricing.price_per_hour, Decimal('30.00'))

        # Valid price update
        res_valid = self.client.post(reverse('admin_pricing'), {
            'car_rate': '45.00',
            'bike_rate': '20.00'
        })
        self.assertEqual(res_valid.status_code, 302)
        self.car_pricing.refresh_from_db()
        self.assertEqual(self.car_pricing.price_per_hour, Decimal('45.00'))

    def test_13_admin_check_in_and_check_out_lifecycle(self):
        """Test vehicle gate check-in (CONFIRMED -> ACTIVE) and check-out (ACTIVE -> COMPLETED)."""
        self.client.login(username='admin', password='adminpassword123')

        booking = Booking.objects.create(
            booking_id='PB20260055',
            customer_name='Gate Lifecycle User',
            phone='9876543210',
            vehicle_number='DL08ZZ1234',
            vehicle_type=VehicleType.CAR,
            parking_slot=self.car_slot_1,
            booking_date=timezone.localdate(),
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
            amount=Decimal('60.00'),
            status=BookingStatus.CONFIRMED
        )

        # 1. Gate Check-in
        check_in_res = self.client.post(reverse('admin_check_in', args=[booking.booking_id]))
        self.assertEqual(check_in_res.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingStatus.ACTIVE)
        self.assertIsNotNone(booking.check_in_time)

        # 2. Gate Check-out
        check_out_res = self.client.post(reverse('admin_check_out', args=[booking.booking_id]))
        self.assertEqual(check_out_res.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingStatus.COMPLETED)
        self.assertIsNotNone(booking.check_out_time)

    def test_14_admin_reports_analytics_calculation(self):
        """Test financial reports accurately aggregate revenue by vehicle type and payment status."""
        self.client.login(username='admin', password='adminpassword123')
        today = timezone.localdate()

        b1 = Booking.objects.create(
            booking_id='PB20260080',
            customer_name='Report Car 1',
            phone='9876543210',
            vehicle_number='KA01AA1111',
            vehicle_type=VehicleType.CAR,
            parking_slot=self.car_slot_1,
            booking_date=today,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
            amount=Decimal('60.00'),
            status=BookingStatus.COMPLETED
        )
        Payment.objects.create(
            transaction_id='TXN20260901',
            booking=b1,
            amount=Decimal('60.00'),
            payment_method=PaymentMethod.UPI,
            payment_status=PaymentStatus.PAID
        )

        res = self.client.get(reverse('admin_reports'), {'daily_date': str(today)})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['daily_revenue'], Decimal('60.00'))
        self.assertEqual(res.context['daily_total_bookings'], 1)

    def test_15_slot_status_for_window_computation(self):
        """Verify dynamic status tags: AVAILABLE, BOOKED, OCCUPIED."""
        today = timezone.localdate()
        
        # Initially Available
        status = get_slot_status_for_window(self.car_slot_1, today, datetime.time(10, 0), datetime.time(12, 0))
        self.assertEqual(status, 'AVAILABLE')

        # When Confirmed -> BOOKED
        b = Booking.objects.create(
            booking_id='PB20260090',
            customer_name='Status Test',
            phone='9876543210',
            vehicle_number='KA01AA2222',
            vehicle_type=VehicleType.CAR,
            parking_slot=self.car_slot_1,
            booking_date=today,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
            amount=Decimal('60.00'),
            status=BookingStatus.CONFIRMED
        )
        status_booked = get_slot_status_for_window(self.car_slot_1, today, datetime.time(10, 0), datetime.time(12, 0))
        self.assertEqual(status_booked, 'BOOKED')

        # When Parked -> OCCUPIED
        b.status = BookingStatus.ACTIVE
        b.save()
        status_occ = get_slot_status_for_window(self.car_slot_1, today, datetime.time(10, 0), datetime.time(12, 0))
        self.assertEqual(status_occ, 'OCCUPIED')

    def test_16_inactive_slot_exclusion(self):
        """Verify inactive slots are excluded from customer search."""
        self.car_slot_2.is_active = False
        self.car_slot_2.save()

        self.assertFalse(is_slot_available(self.car_slot_2, self.future_date, datetime.time(10, 0), datetime.time(12, 0)))
