USE hotel_booking_dbunit_demo;
GO

SELECT DB_NAME() AS database_name,
       OBJECT_ID(N'dbo.create_booking', N'P') AS create_booking_procedure,
       OBJECT_ID(N'dbo.trg_Payment_UpdateBookingStatus', N'TR') AS payment_status_trigger;
SELECT guest_id, full_name, email FROM dbo.Guest ORDER BY guest_id;
SELECT room_id, room_number, price_per_night, active FROM dbo.Room ORDER BY room_id;
SELECT booking_id, guest_id, room_id, check_in, check_out, nights,
       discount_rate, total_amount, status
FROM dbo.Booking ORDER BY booking_id;
SELECT payment_id, booking_id, amount, paid_at FROM dbo.Payment ORDER BY payment_id;
