USE hotel_booking_dbunit_demo;
GO

IF DB_NAME() <> N'hotel_booking_dbunit_demo'
    THROW 51000, 'This seed script must run in hotel_booking_dbunit_demo.', 1;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;

BEGIN TRANSACTION;

-- Reset only the isolated DBUnit demo database, then load the rows from datasets/*.xml.
DELETE FROM dbo.Payment;
DELETE FROM dbo.Booking;
DELETE FROM dbo.Guest;
DELETE FROM dbo.Room;

SET IDENTITY_INSERT dbo.Guest ON;
INSERT dbo.Guest(guest_id, email, full_name, phone) VALUES
    (1, N'an.nguyen@example.test', N'Nguyen Van An', N'0900000001'),
    (2, N'binh.tran@example.test', N'Tran Thi Binh', N'0900000002');
SET IDENTITY_INSERT dbo.Guest OFF;

SET IDENTITY_INSERT dbo.Room ON;
INSERT dbo.Room(room_id, room_number, room_type, price_per_night, active) VALUES
    (1, N'101', N'Standard', 1000000.00, 1),
    (2, N'201', N'Deluxe', 1500000.00, 1),
    (3, N'301', N'Standard', 1000000.00, 0);
SET IDENTITY_INSERT dbo.Room OFF;

SET IDENTITY_INSERT dbo.Booking ON;
INSERT dbo.Booking(booking_id, guest_id, room_id, check_in, check_out, nights,
                   discount_rate, total_amount, status) VALUES
    (100, 1, 1, '2026-11-10', '2026-11-12', 2, 0.0000, 2000000.00, 'BOOKED'),
    (101, 2, 2, '2026-11-10', '2026-11-13', 3, 0.1000, 4050000.00, 'BOOKED');
SET IDENTITY_INSERT dbo.Booking OFF;

SET IDENTITY_INSERT dbo.Payment ON;
INSERT dbo.Payment(payment_id, booking_id, amount) VALUES
    (1000, 100, 500000.00),
    (1001, 101, 1000000.00);
SET IDENTITY_INSERT dbo.Payment OFF;

DBCC CHECKIDENT ('dbo.Guest', RESEED, 2) WITH NO_INFOMSGS;
DBCC CHECKIDENT ('dbo.Room', RESEED, 3) WITH NO_INFOMSGS;
DBCC CHECKIDENT ('dbo.Booking', RESEED, 101) WITH NO_INFOMSGS;
DBCC CHECKIDENT ('dbo.Payment', RESEED, 1001) WITH NO_INFOMSGS;

COMMIT TRANSACTION;
GO
