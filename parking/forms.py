import datetime
import re
from django import forms
from django.utils import timezone
from .models import ParkingSlot, Pricing, VehicleType, PaymentMethod, Booking


class AvailabilitySearchForm(forms.Form):
    booking_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control form-control-lg',
            'type': 'date',
            'id': 'id_booking_date'
        }),
        label="Parking Date"
    )
    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={
            'class': 'form-control form-control-lg',
            'type': 'time',
            'id': 'id_start_time'
        }),
        label="Start Time"
    )
    end_time = forms.TimeField(
        widget=forms.TimeInput(attrs={
            'class': 'form-control form-control-lg',
            'type': 'time',
            'id': 'id_end_time'
        }),
        label="End Time"
    )
    vehicle_type = forms.ChoiceField(
        choices=VehicleType.choices,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-lg',
            'id': 'id_vehicle_type'
        }),
        label="Vehicle Type"
    )

    def clean(self):
        cleaned_data = super().clean()
        booking_date = cleaned_data.get('booking_date')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')

        if not (booking_date and start_time and end_time):
            return cleaned_data

        today = timezone.localdate()
        if booking_date < today:
            self.add_error('booking_date', "Parking date cannot be in the past.")

        if end_time <= start_time:
            self.add_error('end_time', "End time must be later than start time.")

        if booking_date == today:
            now_time = timezone.localtime(timezone.now()).time()
            if start_time < now_time:
                self.add_error('start_time', "Start time cannot be in the past for today's booking.")

        return cleaned_data


class CustomerDetailsForm(forms.Form):
    customer_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your full name',
            'autocomplete': 'name'
        }),
        label="Full Name"
    )
    phone = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '10-digit mobile number, e.g. 9876543210',
            'type': 'tel'
        }),
        label="Phone Number"
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Optional email for digital confirmation'
        }),
        label="Email Address (Optional)"
    )
    vehicle_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-uppercase',
            'placeholder': 'e.g. AP39AB1234 or DL01AB1234'
        }),
        label="Vehicle Registration Number"
    )

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        digits = re.sub(r'\D', '', phone)
        if len(digits) < 10:
            raise forms.ValidationError("Please provide a valid phone number (at least 10 digits).")
        return digits[-10:] if len(digits) >= 10 else digits

    def clean_vehicle_number(self):
        vnum = self.cleaned_data.get('vehicle_number', '').strip().upper()
        cleaned_vnum = re.sub(r'[^A-Z0-9]', '', vnum)
        if len(cleaned_vnum) < 4:
            raise forms.ValidationError("Please enter a valid vehicle registration number.")
        return cleaned_vnum


class PaymentForm(forms.Form):
    payment_method = forms.ChoiceField(
        choices=PaymentMethod.choices,
        widget=forms.RadioSelect(attrs={'class': 'btn-check'}),
        initial=PaymentMethod.UPI
    )


class CheckBookingForm(forms.Form):
    booking_id = forms.CharField(
        required=False,
        max_length=25,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg text-uppercase',
            'placeholder': 'e.g. PB20260001 (Optional)'
        }),
        label="Booking ID"
    )
    phone = forms.CharField(
        required=False,
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': '10-digit mobile number (Optional)',
            'type': 'tel'
        }),
        label="Registered Phone Number"
    )

    def clean(self):
        cleaned_data = super().clean()
        booking_id = cleaned_data.get('booking_id', '').strip().upper()
        phone = cleaned_data.get('phone', '').strip()

        if not booking_id and not phone:
            raise forms.ValidationError("Please provide either your Booking ID or registered Phone Number to search.")

        if phone:
            digits = re.sub(r'\D', '', phone)
            if len(digits) < 10:
                self.add_error('phone', "Please enter a valid phone number (at least 10 digits).")
            else:
                cleaned_data['phone'] = digits[-10:]

        if booking_id:
            cleaned_data['booking_id'] = booking_id

        return cleaned_data


class ParkingSlotForm(forms.ModelForm):
    class Meta:
        model = ParkingSlot
        fields = ['slot_number', 'vehicle_type', 'is_active']
        widgets = {
            'slot_number': forms.TextInput(attrs={'class': 'form-control text-uppercase', 'placeholder': 'e.g. A11'}),
            'vehicle_type': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_slot_number(self):
        slot_number = self.cleaned_data.get('slot_number', '').strip().upper()
        if not slot_number:
            raise forms.ValidationError("Slot number cannot be empty.")
        
        # Check uniqueness excluding current instance on edit
        qs = ParkingSlot.objects.filter(slot_number__iexact=slot_number)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(f"Parking bay '{slot_number}' already exists in the system.")
        
        return slot_number


class PricingForm(forms.ModelForm):
    class Meta:
        model = Pricing
        fields = ['vehicle_type', 'price_per_hour']
        widgets = {
            'vehicle_type': forms.Select(attrs={'class': 'form-select'}),
            'price_per_hour': forms.NumberInput(attrs={'class': 'form-control', 'step': '1.00', 'min': '1.00'}),
        }

    def clean_price_per_hour(self):
        rate = self.cleaned_data.get('price_per_hour')
        if rate is None or rate <= 0:
            raise forms.ValidationError("Price per hour must be greater than zero.")
        return rate
