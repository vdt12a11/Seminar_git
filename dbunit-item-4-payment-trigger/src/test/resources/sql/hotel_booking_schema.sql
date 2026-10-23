-- SQL Server hotel booking demo schema.
-- Run in SQL Server Management Studio or sqlcmd.

IF DB_ID(N'hotel_booking_dbunit_demo') IS NULL
    CREATE DATABASE hotel_booking_dbunit_demo;
GO
USE hotel_booking_dbunit_demo;
GO

CREATE TABLE dbo.Guest (
    guest_id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Guest PRIMARY KEY,
    email NVARCHAR(255) NOT NULL,
    full_name NVARCHAR(150) NOT NULL,
    phone NVARCHAR(30) NULL,
    CONSTRAINT UQ_Guest_email UNIQUE (email)
);
GO

CREATE TABLE dbo.Room (
    room_id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Room PRIMARY KEY,
    room_number NVARCHAR(20) NOT NULL,
    room_type NVARCHAR(50) NOT NULL,
    price_per_night DECIMAL(12,2) NOT NULL,
    active BIT NOT NULL CONSTRAINT DF_Room_active DEFAULT (1),
    CONSTRAINT UQ_Room_room_number UNIQUE (room_number),
    CONSTRAINT CK_Room_price CHECK (price_per_night > 0)
);
GO

CREATE TABLE dbo.Booking (
    booking_id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Booking PRIMARY KEY,
    guest_id BIGINT NOT NULL,
    room_id BIGINT NOT NULL,
    check_in DATE NOT NULL,
    check_out DATE NOT NULL,
    nights INT NOT NULL,
    discount_rate DECIMAL(5,4) NOT NULL CONSTRAINT DF_Booking_discount DEFAULT (0),
    total_amount DECIMAL(12,2) NOT NULL,
    status VARCHAR(10) NOT NULL CONSTRAINT DF_Booking_status DEFAULT ('BOOKED'),
    created_at DATETIME2 NOT NULL CONSTRAINT DF_Booking_created DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT FK_Booking_Guest FOREIGN KEY (guest_id) REFERENCES dbo.Guest(guest_id),
    CONSTRAINT FK_Booking_Room FOREIGN KEY (room_id) REFERENCES dbo.Room(room_id),
    CONSTRAINT CK_Booking_dates CHECK (check_out > check_in),
    CONSTRAINT CK_Booking_discount CHECK (discount_rate BETWEEN 0 AND 1),
    CONSTRAINT CK_Booking_total CHECK (total_amount >= 0),
    CONSTRAINT CK_Booking_status CHECK (status IN ('BOOKED', 'PAID', 'CANCELLED'))
);
CREATE INDEX IX_Booking_room_dates ON dbo.Booking(room_id, check_in, check_out);
GO

CREATE TABLE dbo.Payment (
    payment_id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Payment PRIMARY KEY,
    booking_id BIGINT NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    paid_at DATETIME2 NOT NULL CONSTRAINT DF_Payment_paid DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT FK_Payment_Booking FOREIGN KEY (booking_id) REFERENCES dbo.Booking(booking_id) ON DELETE CASCADE,
    CONSTRAINT CK_Payment_amount CHECK (amount > 0)
);
CREATE INDEX IX_Payment_booking ON dbo.Payment(booking_id);
GO

CREATE OR ALTER PROCEDURE dbo.create_booking
    @guest_id BIGINT,
    @room_id BIGINT,
    @check_in DATE,
    @check_out DATE,
    @initial_payment DECIMAL(12,2) = 0,
    @booking_id BIGINT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    SET @booking_id = NULL;

    BEGIN TRY
        BEGIN TRANSACTION;

        IF @check_in IS NULL OR @check_out IS NULL OR @check_out <= @check_in
            THROW 50001, 'Invalid booking date range.', 1;

        IF NOT EXISTS (SELECT 1 FROM dbo.Guest WHERE guest_id = @guest_id)
            THROW 50002, 'Guest does not exist.', 1;

        DECLARE @price DECIMAL(12,2);
        SELECT @price = price_per_night
        FROM dbo.Room WITH (UPDLOCK, HOLDLOCK)
        WHERE room_id = @room_id AND active = 1;

        IF @price IS NULL
            THROW 50003, 'Room does not exist or is inactive.', 1;

        IF EXISTS (
            SELECT 1 FROM dbo.Booking WITH (UPDLOCK, HOLDLOCK)
            WHERE room_id = @room_id AND status <> 'CANCELLED'
              AND @check_in < check_out AND @check_out > check_in
        )
            THROW 50004, 'Room is already booked for these dates.', 1;

        DECLARE @nights INT = DATEDIFF(DAY, @check_in, @check_out);
        DECLARE @discount DECIMAL(5,4) = CASE WHEN @nights >= 3 THEN 0.1000 ELSE 0.0000 END;
        DECLARE @total DECIMAL(12,2) = ROUND(@nights * @price * (1 - @discount), 2);

        IF @initial_payment < 0 OR @initial_payment > @total
            THROW 50005, 'Initial payment must be between zero and booking total.', 1;

        INSERT dbo.Booking(guest_id, room_id, check_in, check_out, nights, discount_rate, total_amount)
        VALUES (@guest_id, @room_id, @check_in, @check_out, @nights, @discount, @total);
        SET @booking_id = CONVERT(BIGINT, SCOPE_IDENTITY());

        IF @initial_payment > 0
            INSERT dbo.Payment(booking_id, amount) VALUES (@booking_id, @initial_payment);

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
        SET @booking_id = NULL;
        THROW;
    END CATCH;
END;
GO

CREATE OR ALTER TRIGGER dbo.trg_Payment_UpdateBookingStatus
ON dbo.Payment
AFTER INSERT, UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;

    ;WITH ChangedBookings AS (
        SELECT booking_id FROM inserted
        UNION
        SELECT booking_id FROM deleted
    ), PaymentTotals AS (
        SELECT cb.booking_id, COALESCE(SUM(p.amount), 0) AS paid_total
        FROM ChangedBookings cb
        LEFT JOIN dbo.Payment p ON p.booking_id = cb.booking_id
        GROUP BY cb.booking_id
    )
    UPDATE b
    SET status = CASE WHEN pt.paid_total >= b.total_amount THEN 'PAID' ELSE 'BOOKED' END
    FROM dbo.Booking b
    JOIN PaymentTotals pt ON pt.booking_id = b.booking_id
    WHERE b.status <> 'CANCELLED';
END;
GO

-- Example: create a booking with a partial payment.
-- DECLARE @new_booking_id BIGINT;
-- EXEC dbo.create_booking @guest_id=1, @room_id=1,
--     @check_in='2026-11-01', @check_out='2026-11-04',
--     @initial_payment=100000, @booking_id=@new_booking_id OUTPUT;
-- SELECT @new_booking_id AS booking_id;
