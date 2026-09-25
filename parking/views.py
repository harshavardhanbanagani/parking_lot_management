import datetime
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.forms import AuthenticationForm
from django.utils import timezone
from django.db.models import Count, Sum, Q
from django.db import transaction

from .models import (
    ParkingSlot, Booking, Payment, Pricing,
    VehicleType, BookingStatus, PaymentMethod, PaymentStatus
)
from .forms import (
    AvailabilitySearchForm, CustomerDetailsForm, PaymentForm,
    CheckBookingForm, ParkingSlotForm, PricingForm
)
from .utils import (
    generate_booking_id, generate_transaction_id,
    calculate_duration_and_amount, is_slot_available,
    is_vehicle_already_booked, get_slot_status_for_window,
    get_current_pricing
)


# ==========================================
# CUSTOMER VIEWS
# ==========================================

def home_view(request):
    """Landing page with facility overview, rates, and quick booking search."""
    car_rate = get_current_pricing(VehicleType.CAR)
    bike_rate = get_current_pricing(VehicleType.BIKE)
    
    total_slots = ParkingSlot.objects.filter(is_active=True).count()
    car_slots = ParkingSlot.objects.filter(is_active=True, vehicle_type=VehicleType.CAR).count()
    bike_slots = ParkingSlot.objects.filter(is_active=True, vehicle_type=VehicleType.BIKE).count()
    
    today = timezone.localdate()
    initial_start = (timezone.localtime(timezone.now()) + datetime.timedelta(minutes=30)).strftime('%H:%M')
    initial_end = (timezone.localtime(timezone.now()) + datetime.timedelta(hours=2, minutes=30)).strftime('%H:%M')

    context = {
        'car_rate': car_rate,
        'bike_rate': bike_rate,
        'total_slots': total_slots,
        'car_slots': car_slots,
        'bike_slots': bike_slots,
        'today': today.strftime('%Y-%m-%d'),
        'initial_start': initial_start,
        'initial_end': initial_end,
    }
    return render(request, 'home.html', context)


def check_availability_view(request):
    """Step 1 & 2: Search date/time and display calculated parking slot layout."""
    form = AvailabilitySearchForm(request.GET or None)
    slots_with_status = []
    searched = False
    duration_hours = Decimal('1.0')
    search_params = {}
    rate = Decimal('30.00')

    if request.GET and form.is_valid():
        searched = True
        booking_date = form.cleaned_data['booking_date']
        start_time = form.cleaned_data['start_time']
        end_time = form.cleaned_data['end_time']
        vehicle_type = form.cleaned_data['vehicle_type']

        duration_hours, rate, total_amount = calculate_duration_and_amount(vehicle_type, start_time, end_time)

        # Store in session for booking flow
        search_params = {
            'booking_date': booking_date.strftime('%Y-%m-%d'),
            'start_time': start_time.strftime('%H:%M'),
            'end_time': end_time.strftime('%H:%M'),
            'vehicle_type': vehicle_type,
            'duration_hours': float(duration_hours),
            'rate': float(rate),
            'total_amount': float(total_amount),
        }
        request.session['search_params'] = search_params

        # Get all operational slots for vehicle type
        slots = ParkingSlot.objects.filter(
            is_active=True,
            vehicle_type=vehicle_type
        ).order_by('slot_number')

        for slot in slots:
            status = get_slot_status_for_window(slot, booking_date, start_time, end_time)
            slots_with_status.append({
                'slot': slot,
                'status': status,  # AVAILABLE (Green), BOOKED (Red), OCCUPIED (Gray)
                'total_amount': total_amount,
                'rate': rate,
            })

    context = {
        'form': form,
        'searched': searched,
        'slots_with_status': slots_with_status,
        'search_params': search_params,
        'duration_hours': duration_hours,
        'rate': rate,
    }
    return render(request, 'booking/check_availability.html', context)


def select_slot_view(request, slot_id):
    """Step 3 & 4: Slot selected, collect customer and vehicle details."""
    search_params = request.session.get('search_params')
    if not search_params:
        messages.warning(request, "Please select date and time before choosing a slot.")
        return redirect('check_availability')

    slot = get_object_or_404(ParkingSlot, id=slot_id, is_active=True)

    booking_date = datetime.datetime.strptime(search_params['booking_date'], '%Y-%m-%d').date()
    start_time = datetime.datetime.strptime(search_params['start_time'], '%H:%M').time()
    end_time = datetime.datetime.strptime(search_params['end_time'], '%H:%M').time()
    vehicle_type = search_params['vehicle_type']

    # Pre-check slot availability
    if not is_slot_available(slot, booking_date, start_time, end_time):
        messages.error(request, f"Slot {slot.slot_number} is no longer available for the selected time window. Please choose another slot.")
        return redirect('check_availability')

    duration_hours, rate, total_amount = calculate_duration_and_amount(vehicle_type, start_time, end_time)

    form = CustomerDetailsForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        vehicle_num = form.cleaned_data['vehicle_number']

        # Enforce Vehicle Overlap Rule: Same vehicle cannot have overlapping bookings
        if is_vehicle_already_booked(vehicle_num, booking_date, start_time, end_time):
            form.add_error('vehicle_number', f"Vehicle {vehicle_num} already has an active or confirmed reservation during this time window.")
        else:
            request.session['booking_flow'] = {
                'slot_id': slot.id,
                'slot_number': slot.slot_number,
                'booking_date': search_params['booking_date'],
                'start_time': search_params['start_time'],
                'end_time': search_params['end_time'],
                'vehicle_type': vehicle_type,
                'duration_hours': float(duration_hours),
                'rate': float(rate),
                'total_amount': float(total_amount),
                'customer_name': form.cleaned_data['customer_name'],
                'phone': form.cleaned_data['phone'],
                'email': form.cleaned_data['email'],
                'vehicle_number': vehicle_num,
            }
            return redirect('booking_review')

    context = {
        'slot': slot,
        'search_params': search_params,
        'duration_hours': duration_hours,
        'rate': rate,
        'total_amount': total_amount,
        'form': form,
    }
    return render(request, 'booking/customer_details.html', context)


def booking_review_view(request):
    """Step 5: Review booking summary before proceeding to demo payment."""
    booking_flow = request.session.get('booking_flow')
    if not booking_flow:
        messages.warning(request, "Session expired. Please select your slot again.")
        return redirect('check_availability')

    slot = get_object_or_404(ParkingSlot, id=booking_flow['slot_id'])

    context = {
        'booking': booking_flow,
        'slot': slot,
    }
    return render(request, 'booking/review_booking.html', context)


def payment_view(request):
    """Step 6: Demo payment simulation with concurrency & vehicle overlap protection."""
    booking_flow = request.session.get('booking_flow')
    if not booking_flow:
        messages.warning(request, "No active booking in progress.")
        return redirect('check_availability')

    slot = get_object_or_404(ParkingSlot, id=booking_flow['slot_id'])
    form = PaymentForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        payment_method = form.cleaned_data['payment_method']
        
        booking_date = datetime.datetime.strptime(booking_flow['booking_date'], '%Y-%m-%d').date()
        start_time = datetime.datetime.strptime(booking_flow['start_time'], '%H:%M').time()
        end_time = datetime.datetime.strptime(booking_flow['end_time'], '%H:%M').time()
        vehicle_num = booking_flow['vehicle_number']

        # Concurrency & Validation Protection
        with transaction.atomic():
            # 1. Check Slot Availability
            if not is_slot_available(slot, booking_date, start_time, end_time):
                messages.error(
                    request,
                    f"Sorry, Slot {slot.slot_number} was just booked by another user for this time. Please choose another slot."
                )
                if 'booking_flow' in request.session:
                    del request.session['booking_flow']
                return redirect('check_availability')

            # 2. Check Vehicle Duplicate Overlap
            if is_vehicle_already_booked(vehicle_num, booking_date, start_time, end_time):
                messages.error(
                    request,
                    f"Vehicle {vehicle_num} already has an active or confirmed booking during this time period."
                )
                if 'booking_flow' in request.session:
                    del request.session['booking_flow']
                return redirect('check_availability')

            # 3. Create Confirmed Booking
            booking_id = generate_booking_id()
            booking = Booking.objects.create(
                booking_id=booking_id,
                customer_name=booking_flow['customer_name'],
                phone=booking_flow['phone'],
                email=booking_flow['email'],
                vehicle_number=vehicle_num,
                vehicle_type=booking_flow['vehicle_type'],
                parking_slot=slot,
                booking_date=booking_date,
                start_time=start_time,
                end_time=end_time,
                amount=Decimal(str(booking_flow['total_amount'])),
                status=BookingStatus.CONFIRMED
            )

            # 4. Record Payment
            txn_id = generate_transaction_id()
            Payment.objects.create(
                transaction_id=txn_id,
                booking=booking,
                amount=booking.amount,
                payment_method=payment_method,
                payment_status=PaymentStatus.PAID
            )

        # Clear session
        if 'booking_flow' in request.session:
            del request.session['booking_flow']

        messages.success(request, f"Demo payment successful! Booking confirmed with ID {booking.booking_id}.")
        return redirect('booking_confirmation', booking_id=booking.booking_id)

    context = {
        'booking': booking_flow,
        'slot': slot,
        'form': form,
    }
    return render(request, 'booking/payment.html', context)


def booking_confirmation_view(request, booking_id):
    """Step 7: Booking confirmation page with printable receipt."""
    if booking_id.isdigit():
        booking = get_object_or_404(Booking, Q(id=int(booking_id)) | Q(booking_id=booking_id))
    else:
        booking = get_object_or_404(Booking, booking_id=booking_id)
    payment = getattr(booking, 'payment', None)

    context = {
        'booking': booking,
        'payment': payment,
    }
    return render(request, 'booking/confirmation.html', context)


def check_booking_view(request):
    """Customer lookup for reservations via Booking ID and/or Phone Number."""
    form = CheckBookingForm(request.GET or None)
    bookings = []
    searched = False

    if request.GET and form.is_valid():
        searched = True
        booking_id = form.cleaned_data.get('booking_id')
        phone = form.cleaned_data.get('phone')
        
        query_filters = Q()
        if booking_id and phone:
            query_filters = Q(booking_id__iexact=booking_id) & Q(phone__endswith=phone[-10:])
        elif booking_id:
            query_filters = Q(booking_id__iexact=booking_id)
        elif phone:
            query_filters = Q(phone__endswith=phone[-10:])

        bookings = Booking.objects.filter(query_filters).select_related('parking_slot', 'payment').order_by('-booking_date', '-start_time')

        if not bookings.exists():
            messages.error(request, "No bookings found matching the provided details. Please check your Booking ID or Phone Number.")

    context = {
        'form': form,
        'bookings': bookings,
        'searched': searched,
    }
    return render(request, 'booking/check_booking.html', context)


def cancel_booking_view(request, booking_id):
    """Customer cancellation of future confirmed booking."""
    if booking_id.isdigit():
        booking = get_object_or_404(Booking, Q(id=int(booking_id)) | Q(booking_id=booking_id))
    else:
        booking = get_object_or_404(Booking, booking_id=booking_id)

    if request.method == 'POST':
        if not booking.can_be_cancelled():
            messages.error(request, "This booking cannot be cancelled because it has already started, is active, or was previously completed/cancelled.")
            return redirect('check_booking')

        booking.status = BookingStatus.CANCELLED
        booking.save()

        messages.success(request, f"Booking {booking.booking_id} has been cancelled. Slot {booking.parking_slot.slot_number} is now available again.")
        return redirect(f"{redirect('check_booking').url}?booking_id={booking.booking_id}&phone={booking.phone}")

    messages.warning(request, "Invalid cancellation request.")
    return redirect('check_booking')


# ==========================================
# ADMIN AUTHENTICATION & DASHBOARD
# ==========================================

def admin_login_view(request):
    """Admin login portal."""
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('admin_dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user.is_staff:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect(request.GET.get('next', 'admin_dashboard'))
            else:
                messages.error(request, "Access restricted. Staff account required.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()

    return render(request, 'admin/login.html', {'form': form})


def admin_logout_view(request):
    """Admin logout."""
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('admin_login')


@staff_member_required(login_url='admin_login')
def admin_dashboard_view(request):
    """Admin dashboard showing current database-based parking metrics."""
    today = timezone.localdate()

    total_slots = ParkingSlot.objects.count()
    active_slots_count = ParkingSlot.objects.filter(is_active=True).count()

    # Current database-based metrics for today
    today_active_bookings = Booking.objects.filter(
        booking_date=today,
        status=BookingStatus.ACTIVE
    )
    occupied_count = today_active_bookings.count()

    today_confirmed_bookings = Booking.objects.filter(
        booking_date=today,
        status=BookingStatus.CONFIRMED
    )
    booked_count = today_confirmed_bookings.count()

    available_count = max(0, active_slots_count - (occupied_count + booked_count))

    # Daily counts & revenue
    today_bookings_count = Booking.objects.filter(booking_date=today).count()
    today_revenue = Payment.objects.filter(
        booking__booking_date=today,
        payment_status=PaymentStatus.PAID
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Total counts
    total_customers_count = Booking.objects.values('phone').distinct().count()
    total_revenue_all = Payment.objects.filter(payment_status=PaymentStatus.PAID).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Recent bookings for quick check-in / check-out
    recent_bookings = Booking.objects.all().order_by('-id')[:10]

    context = {
        'total_slots': total_slots,
        'available_slots': available_count,
        'booked_slots': booked_count,
        'occupied_slots': occupied_count,
        'today_bookings': today_bookings_count,
        'today_revenue': today_revenue,
        'total_customers': total_customers_count,
        'total_revenue_all': total_revenue_all,
        'recent_bookings': recent_bookings,
        'today': today,
    }
    return render(request, 'admin/dashboard.html', context)


# ==========================================
# ADMIN MANAGE SLOTS & PRICING
# ==========================================

@staff_member_required(login_url='admin_login')
def admin_slots_view(request):
    """View and filter all parking slots."""
    v_type = request.GET.get('vehicle_type')
    status_filter = request.GET.get('is_active')

    slots = ParkingSlot.objects.all()
    if v_type in [VehicleType.CAR, VehicleType.BIKE]:
        slots = slots.filter(vehicle_type=v_type)
    if status_filter in ['true', '1']:
        slots = slots.filter(is_active=True)
    elif status_filter in ['false', '0']:
        slots = slots.filter(is_active=False)

    car_rate = get_current_pricing(VehicleType.CAR)
    bike_rate = get_current_pricing(VehicleType.BIKE)

    context = {
        'slots': slots,
        'selected_v_type': v_type,
        'selected_status': status_filter,
        'car_rate': car_rate,
        'bike_rate': bike_rate,
    }
    return render(request, 'admin/slots.html', context)


@staff_member_required(login_url='admin_login')
def admin_add_slot_view(request):
    """Add a new parking slot."""
    form = ParkingSlotForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        slot = form.save()
        messages.success(request, f"Parking Slot {slot.slot_number} added successfully.")
        return redirect('admin_slots')

    return render(request, 'admin/slot_form.html', {'form': form, 'action': 'Add'})


@staff_member_required(login_url='admin_login')
def admin_edit_slot_view(request, slot_id):
    """Edit existing parking slot."""
    slot = get_object_or_404(ParkingSlot, id=slot_id)
    form = ParkingSlotForm(request.POST or None, instance=slot)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f"Parking Slot {slot.slot_number} updated successfully.")
        return redirect('admin_slots')

    return render(request, 'admin/slot_form.html', {'form': form, 'slot': slot, 'action': 'Edit'})


@staff_member_required(login_url='admin_login')
def admin_delete_slot_view(request, slot_id):
    """Delete parking slot if no active bookings exist."""
    slot = get_object_or_404(ParkingSlot, id=slot_id)
    if request.method == 'POST':
        if slot.bookings.filter(status__in=[BookingStatus.CONFIRMED, BookingStatus.ACTIVE]).exists():
            messages.error(request, f"Cannot delete Slot {slot.slot_number} because it has active or confirmed bookings. Deactivate it instead.")
        else:
            slot_num = slot.slot_number
            slot.delete()
            messages.success(request, f"Slot {slot_num} deleted successfully.")
    return redirect('admin_slots')


@staff_member_required(login_url='admin_login')
def admin_pricing_view(request):
    """Single place for admin to manage hourly rates for Car and Bike."""
    car_pricing, _ = Pricing.objects.get_or_create(
        vehicle_type=VehicleType.CAR,
        defaults={'price_per_hour': Decimal('30.00')}
    )
    bike_pricing, _ = Pricing.objects.get_or_create(
        vehicle_type=VehicleType.BIKE,
        defaults={'price_per_hour': Decimal('15.00')}
    )

    if request.method == 'POST':
        car_rate_str = request.POST.get('car_rate', '').strip()
        bike_rate_str = request.POST.get('bike_rate', '').strip()
        try:
            car_rate = Decimal(car_rate_str)
            bike_rate = Decimal(bike_rate_str)
            if car_rate <= 0 or bike_rate <= 0:
                messages.error(request, "Hourly rates must be strictly greater than ₹0.00.")
            else:
                car_pricing.price_per_hour = car_rate
                bike_pricing.price_per_hour = bike_rate
                car_pricing.save()
                bike_pricing.save()
                messages.success(request, f"Pricing rates updated: Car ₹{car_rate}/hr, Bike ₹{bike_rate}/hr.")
        except Exception as e:
            messages.error(request, f"Invalid pricing value entered: {e}")
        return redirect('admin_pricing')

    context = {
        'car_pricing': car_pricing,
        'bike_pricing': bike_pricing,
    }
    return render(request, 'admin/pricing.html', context)


# ==========================================
# ADMIN BOOKINGS & CHECK-IN / CHECK-OUT
# ==========================================

@staff_member_required(login_url='admin_login')
def admin_bookings_view(request):
    """View bookings with search and status/date filters."""
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    date_filter = request.GET.get('date', '').strip()

    bookings = Booking.objects.select_related('parking_slot', 'payment').all()

    if query:
        bookings = bookings.filter(
            Q(booking_id__icontains=query) |
            Q(customer_name__icontains=query) |
            Q(phone__icontains=query) |
            Q(vehicle_number__icontains=query) |
            Q(parking_slot__slot_number__icontains=query)
        )

    if status_filter:
        bookings = bookings.filter(status=status_filter)

    if date_filter:
        try:
            parsed_date = datetime.datetime.strptime(date_filter, '%Y-%m-%d').date()
            bookings = bookings.filter(booking_date=parsed_date)
        except ValueError:
            pass

    context = {
        'bookings': bookings,
        'query': query,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'statuses': BookingStatus.choices,
    }
    return render(request, 'admin/bookings.html', context)


@staff_member_required(login_url='admin_login')
def admin_booking_detail_view(request, booking_id):
    """Admin view for detailed booking information."""
    booking = get_object_or_404(Booking.objects.select_related('parking_slot', 'payment'), booking_id=booking_id)
    return render(request, 'admin/booking_detail.html', {'booking': booking})


@staff_member_required(login_url='admin_login')
def admin_check_in_view(request, booking_id):
    """Check-in vehicle: CONFIRMED -> ACTIVE, record check_in_time."""
    booking = get_object_or_404(Booking, booking_id=booking_id)
    if request.method == 'POST':
        if booking.status != BookingStatus.CONFIRMED:
            messages.error(request, f"Booking {booking.booking_id} cannot be checked in because its status is {booking.get_status_display()}.")
        else:
            booking.status = BookingStatus.ACTIVE
            booking.check_in_time = timezone.now()
            booking.save()
            messages.success(request, f"Vehicle {booking.vehicle_number} checked in successfully for Slot {booking.parking_slot.slot_number}.")
    return redirect(request.META.get('HTTP_REFERER', 'admin_bookings'))


@staff_member_required(login_url='admin_login')
def admin_check_out_view(request, booking_id):
    """Check-out vehicle: ACTIVE -> COMPLETED, record check_out_time."""
    booking = get_object_or_404(Booking, booking_id=booking_id)
    if request.method == 'POST':
        if booking.status != BookingStatus.ACTIVE:
            messages.error(request, f"Booking {booking.booking_id} cannot be checked out because its status is {booking.get_status_display()}.")
        else:
            booking.status = BookingStatus.COMPLETED
            booking.check_out_time = timezone.now()
            booking.save()
            messages.success(request, f"Vehicle {booking.vehicle_number} checked out successfully from Slot {booking.parking_slot.slot_number}.")
    return redirect(request.META.get('HTTP_REFERER', 'admin_bookings'))


# ==========================================
# ADMIN CUSTOMERS, PAYMENTS & REPORTS
# ==========================================

@staff_member_required(login_url='admin_login')
def admin_customers_view(request):
    """Aggregated customer directory extracted from booking records."""
    query = request.GET.get('q', '').strip()
    
    customers = Booking.objects.values(
        'phone', 'customer_name', 'email', 'vehicle_number', 'vehicle_type'
    ).annotate(
        total_bookings=Count('id'),
        total_spent=Sum('amount')
    ).order_by('-total_bookings')

    if query:
        customers = customers.filter(
            Q(customer_name__icontains=query) |
            Q(phone__icontains=query) |
            Q(vehicle_number__icontains=query)
        )

    context = {
        'customers': customers,
        'query': query,
    }
    return render(request, 'admin/customers.html', context)


@staff_member_required(login_url='admin_login')
def admin_payments_view(request):
    """View payment transactions audit log."""
    query = request.GET.get('q', '').strip()
    method_filter = request.GET.get('method', '').strip()

    payments = Payment.objects.select_related('booking', 'booking__parking_slot').all().order_by('-payment_date')

    if query:
        payments = payments.filter(
            Q(transaction_id__icontains=query) |
            Q(booking__booking_id__icontains=query) |
            Q(booking__customer_name__icontains=query)
        )

    if method_filter:
        payments = payments.filter(payment_method=method_filter)

    total_amount = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    context = {
        'payments': payments,
        'query': query,
        'method_filter': method_filter,
        'total_amount': total_amount,
        'methods': PaymentMethod.choices,
    }
    return render(request, 'admin/payments.html', context)


@staff_member_required(login_url='admin_login')
def admin_reports_view(request):
    """Daily and Monthly operational and financial reports."""
    # Daily Report parameters
    selected_date_str = request.GET.get('daily_date')
    if selected_date_str:
        try:
            daily_date = datetime.datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except ValueError:
            daily_date = timezone.localdate()
    else:
        daily_date = timezone.localdate()

    daily_bookings = Booking.objects.filter(booking_date=daily_date)
    daily_total_bookings = daily_bookings.count()
    daily_completed = daily_bookings.filter(status=BookingStatus.COMPLETED).count()
    daily_cancelled = daily_bookings.filter(status=BookingStatus.CANCELLED).count()
    daily_active = daily_bookings.filter(status=BookingStatus.ACTIVE).count()
    daily_confirmed = daily_bookings.filter(status=BookingStatus.CONFIRMED).count()
    daily_revenue = Payment.objects.filter(
        booking__booking_date=daily_date,
        payment_status=PaymentStatus.PAID
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Monthly Report parameters
    today = timezone.localdate()
    selected_month = int(request.GET.get('month', today.month))
    selected_year = int(request.GET.get('year', today.year))

    monthly_bookings = Booking.objects.filter(
        booking_date__year=selected_year,
        booking_date__month=selected_month
    )
    monthly_total_bookings = monthly_bookings.count()
    monthly_revenue = Payment.objects.filter(
        booking__booking_date__year=selected_year,
        booking__booking_date__month=selected_month,
        payment_status=PaymentStatus.PAID
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    monthly_car_bookings = monthly_bookings.filter(vehicle_type=VehicleType.CAR).count()
    monthly_bike_bookings = monthly_bookings.filter(vehicle_type=VehicleType.BIKE).count()
    monthly_car_revenue = Payment.objects.filter(
        booking__booking_date__year=selected_year,
        booking__booking_date__month=selected_month,
        booking__vehicle_type=VehicleType.CAR,
        payment_status=PaymentStatus.PAID
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    monthly_bike_revenue = Payment.objects.filter(
        booking__booking_date__year=selected_year,
        booking__booking_date__month=selected_month,
        booking__vehicle_type=VehicleType.BIKE,
        payment_status=PaymentStatus.PAID
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    context = {
        'daily_date': daily_date,
        'daily_total_bookings': daily_total_bookings,
        'daily_completed': daily_completed,
        'daily_cancelled': daily_cancelled,
        'daily_active': daily_active,
        'daily_confirmed': daily_confirmed,
        'daily_revenue': daily_revenue,
        
        'selected_month': selected_month,
        'selected_year': selected_year,
        'monthly_total_bookings': monthly_total_bookings,
        'monthly_revenue': monthly_revenue,
        'monthly_car_bookings': monthly_car_bookings,
        'monthly_bike_bookings': monthly_bike_bookings,
        'monthly_car_revenue': monthly_car_revenue,
        'monthly_bike_revenue': monthly_bike_revenue,
        'months': range(1, 13),
        'years': range(today.year - 2, today.year + 2),
    }
    return render(request, 'admin/reports.html', context)
