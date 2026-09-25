from django.urls import path
from . import views

urlpatterns = [
    # Customer Public Routes
    path('', views.home_view, name='home'),
    path('availability/', views.check_availability_view, name='check_availability'),
    path('select-slot/<int:slot_id>/', views.select_slot_view, name='select_slot'),
    path('review/', views.booking_review_view, name='booking_review'),
    path('payment/', views.payment_view, name='payment'),
    path('confirmation/<str:booking_id>/', views.booking_confirmation_view, name='booking_confirmation'),
    path('check-booking/', views.check_booking_view, name='check_booking'),
    path('cancel-booking/<str:booking_id>/', views.cancel_booking_view, name='cancel_booking'),

    # Admin Protected Routes
    path('admin-login/', views.admin_login_view, name='admin_login'),
    path('admin-logout/', views.admin_logout_view, name='admin_logout'),
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('admin-slots/', views.admin_slots_view, name='admin_slots'),
    path('admin-slots/add/', views.admin_add_slot_view, name='admin_add_slot'),
    path('admin-slots/edit/<int:slot_id>/', views.admin_edit_slot_view, name='admin_edit_slot'),
    path('admin-slots/delete/<int:slot_id>/', views.admin_delete_slot_view, name='admin_delete_slot'),
    path('admin-pricing/', views.admin_pricing_view, name='admin_pricing'),
    path('admin-bookings/', views.admin_bookings_view, name='admin_bookings'),
    path('admin-bookings/<str:booking_id>/', views.admin_booking_detail_view, name='admin_booking_detail'),
    path('admin-bookings/<str:booking_id>/check-in/', views.admin_check_in_view, name='admin_check_in'),
    path('admin-bookings/<str:booking_id>/check-out/', views.admin_check_out_view, name='admin_check_out'),
    path('admin-customers/', views.admin_customers_view, name='admin_customers'),
    path('admin-payments/', views.admin_payments_view, name='admin_payments'),
    path('admin-reports/', views.admin_reports_view, name='admin_reports'),
]
