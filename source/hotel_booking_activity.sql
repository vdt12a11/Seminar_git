/*
    HOTEL BOOKING DATABASE - ACTIVITY VERSION
    Microsoft SQL Server 2016 SP1 or later

    Business requirements
    ---------------------
    - Guest email is required, valid, and unique; a guest name is required.
    - Room numbers are unique. Only active rooms can be booked.
    - A booking refers to an existing guest and room.
    - Check-out is after check-in. Nights equal the date difference.
    - A room cannot have overlapping bookings unless an earlier booking is cancelled.
    - The room's price at booking time is retained for that booking.
    - Booking total equals nights * price at booking * (1 - discount rate).
    - Discount rate is between 0 and 1; stays of at least 3 nights receive 10% off.
    - Payments are positive and total payments cannot exceed the booking amount.
    - A booking is PAID when payments cover the total; otherwise it remains BOOKED.
    - A cancelled booking cannot accept payments.

    The activity schema includes both enforced and unenforced rules. Participants
    should derive coverage from the business requirements above.
*/

IF DB_ID(N'hotel_booking_activity') IS NULL
    CREATE DATABASE hotel_booking_activity;
GO

USE hotel_booking_activity;
GO

IF OBJECT_ID(N'dbo.Guest', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Guest
    (
        guest_id   INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Guest PRIMARY KEY,
        email      NVARCHAR(255) NOT NULL,
        full_name  NVARCHAR(100) NOT NULL,
        phone      NVARCHAR(30) NULL,
        CONSTRAINT UQ_Guest_email UNIQUE (email),
        CONSTRAINT CK_Guest_full_name CHECK (LEN(LTRIM(RTRIM(full_name))) > 0)
    );
END;
GO

/* Reference catalog for valid room types.
   Intentional activity defect: dbo.Room.room_type remains free text and has
   no foreign key or validation against this catalog. */
IF OBJECT_ID(N'dbo.RoomType', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.RoomType
    (
        room_type_id INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_RoomType PRIMARY KEY,
        type_name    NVARCHAR(30) NOT NULL CONSTRAINT UQ_RoomType_type_name UNIQUE
    );
END;
GO

IF OBJECT_ID(N'dbo.Room', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Room
    (
        room_id          INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Room PRIMARY KEY,
        room_number      NVARCHAR(10) NOT NULL,
        room_type        NVARCHAR(30) NOT NULL,
        price_per_night  DECIMAL(10,2) NOT NULL,
        active           BIT NOT NULL CONSTRAINT DF_Room_active DEFAULT (1),
        CONSTRAINT UQ_Room_room_number UNIQUE (room_number),
        CONSTRAINT CK_Room_price CHECK (price_per_night > 0)
    );
END;
GO

IF OBJECT_ID(N'dbo.Booking', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Booking
    (
        booking_id     INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Booking PRIMARY KEY,
        booking_code   NVARCHAR(20) NOT NULL,
        guest_id       INT NOT NULL,
        room_id        INT NOT NULL,
        check_in       DATE NOT NULL,
        check_out      DATE NOT NULL,
        nights         INT NOT NULL,
        discount_rate  DECIMAL(5,4) NOT NULL CONSTRAINT DF_Booking_discount DEFAULT (0),
        total_amount   DECIMAL(10,2) NOT NULL,
        status         VARCHAR(10) NOT NULL CONSTRAINT DF_Booking_status DEFAULT ('BOOKED'),
        created_at     DATETIME2(0) NOT NULL CONSTRAINT DF_Booking_created DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT UQ_Booking_code UNIQUE (booking_code),
        CONSTRAINT FK_Booking_Guest FOREIGN KEY (guest_id) REFERENCES dbo.Guest(guest_id),
        CONSTRAINT FK_Booking_Room FOREIGN KEY (room_id) REFERENCES dbo.Room(room_id),
        CONSTRAINT CK_Booking_dates CHECK (check_out > check_in),
        CONSTRAINT CK_Booking_nights CHECK (nights > 0),
        CONSTRAINT CK_Booking_discount CHECK (discount_rate BETWEEN 0 AND 1),
        CONSTRAINT CK_Booking_total CHECK (total_amount >= 0),
        CONSTRAINT CK_Booking_status CHECK (status IN ('BOOKED', 'PAID', 'CANCELLED'))
    );
END;
GO

IF OBJECT_ID(N'dbo.Payment', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Payment
    (
        payment_id  INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Payment PRIMARY KEY,
        booking_id  INT NOT NULL,
        amount      DECIMAL(10,2) NOT NULL,
        paid_at     DATETIME2(0) NOT NULL CONSTRAINT DF_Payment_paid DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT FK_Payment_Booking FOREIGN KEY (booking_id)
            REFERENCES dbo.Booking(booking_id) ON DELETE CASCADE,
        CONSTRAINT CK_Payment_amount CHECK (amount > 0)
    );
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.Booking') AND name = N'IX_Booking_room_dates')
    CREATE INDEX IX_Booking_room_dates ON dbo.Booking(room_id, check_in, check_out);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.Payment') AND name = N'IX_Payment_booking')
    CREATE INDEX IX_Payment_booking ON dbo.Payment(booking_id);
GO

/* Keep a booking's payment status synchronized with its payment rows. */
CREATE OR ALTER TRIGGER dbo.trg_Payment_UpdateBookingStatus
ON dbo.Payment
AFTER INSERT, UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;

    ;WITH ChangedBookings AS
    (
        SELECT booking_id FROM inserted
        UNION
        SELECT booking_id FROM deleted
    ),
    PaymentTotals AS
    (
        SELECT cb.booking_id, COALESCE(SUM(p.amount), 0) AS paid_total
        FROM ChangedBookings AS cb
        LEFT JOIN dbo.Payment AS p ON p.booking_id = cb.booking_id
        GROUP BY cb.booking_id
    )
    UPDATE b
    SET status = CASE
        WHEN pt.paid_total >= b.total_amount THEN 'PAID'
        ELSE 'BOOKED'
    END
    FROM dbo.Booking AS b
    INNER JOIN PaymentTotals AS pt ON pt.booking_id = b.booking_id
    WHERE b.status <> 'CANCELLED';
END;
GO

/* Valid baseline records for activity participants. */
IF NOT EXISTS (SELECT 1 FROM dbo.RoomType WHERE type_name = N'Standard')
    INSERT INTO dbo.RoomType (type_name) VALUES (N'Standard');

IF NOT EXISTS (SELECT 1 FROM dbo.RoomType WHERE type_name = N'Deluxe')
    INSERT INTO dbo.RoomType (type_name) VALUES (N'Deluxe');

IF NOT EXISTS (SELECT 1 FROM dbo.RoomType WHERE type_name = N'Family')
    INSERT INTO dbo.RoomType (type_name) VALUES (N'Family');

IF NOT EXISTS (SELECT 1 FROM dbo.Guest WHERE email = N'anna@example.test')
    INSERT INTO dbo.Guest (email, full_name, phone)
    VALUES (N'anna@example.test', N'Anna Nguyen', N'0900000101');

IF NOT EXISTS (SELECT 1 FROM dbo.Guest WHERE email = N'minh@example.test')
    INSERT INTO dbo.Guest (email, full_name, phone)
    VALUES (N'minh@example.test', N'Minh Tran', N'0900000102');

IF NOT EXISTS (SELECT 1 FROM dbo.Guest WHERE email = N'linh@example.test')
    INSERT INTO dbo.Guest (email, full_name, phone)
    VALUES (N'linh@example.test', N'Linh Pham', N'0900000103');

IF NOT EXISTS (SELECT 1 FROM dbo.Room WHERE room_number = N'101')
    INSERT INTO dbo.Room (room_number, room_type, price_per_night, active)
    VALUES (N'101', N'Standard', 1000000, 1);

IF NOT EXISTS (SELECT 1 FROM dbo.Room WHERE room_number = N'102')
    INSERT INTO dbo.Room (room_number, room_type, price_per_night, active)
    VALUES (N'102', N'Deluxe', 1600000, 1);

IF NOT EXISTS (SELECT 1 FROM dbo.Room WHERE room_number = N'201')
    INSERT INTO dbo.Room (room_number, room_type, price_per_night, active)
    VALUES (N'201', N'Family', 2200000, 0);
GO

IF NOT EXISTS (SELECT 1 FROM dbo.Booking WHERE booking_code = N'HTL-1001')
BEGIN
    INSERT INTO dbo.Booking
        (booking_code, guest_id, room_id, check_in, check_out, nights, discount_rate, total_amount)
    SELECT N'HTL-1001', g.guest_id, r.room_id,
           DATEADD(DAY, 7, CONVERT(date, GETDATE())),
           DATEADD(DAY, 10, CONVERT(date, GETDATE())),
           3, 0.1000, 2700000
    FROM dbo.Guest AS g
    CROSS JOIN dbo.Room AS r
    WHERE g.email = N'anna@example.test' AND r.room_number = N'101';
END;

IF NOT EXISTS (SELECT 1 FROM dbo.Booking WHERE booking_code = N'HTL-1002')
BEGIN
    INSERT INTO dbo.Booking
        (booking_code, guest_id, room_id, check_in, check_out, nights, discount_rate, total_amount)
    SELECT N'HTL-1002', g.guest_id, r.room_id,
           DATEADD(DAY, 12, CONVERT(date, GETDATE())),
           DATEADD(DAY, 14, CONVERT(date, GETDATE())),
           2, 0.0000, 3200000
    FROM dbo.Guest AS g
    CROSS JOIN dbo.Room AS r
    WHERE g.email = N'minh@example.test' AND r.room_number = N'102';
END;
GO

IF NOT EXISTS
(
    SELECT 1 FROM dbo.Payment AS p
    INNER JOIN dbo.Booking AS b ON b.booking_id = p.booking_id
    WHERE b.booking_code = N'HTL-1001'
)
    INSERT INTO dbo.Payment (booking_id, amount)
    SELECT booking_id, 500000
    FROM dbo.Booking WHERE booking_code = N'HTL-1001';

IF NOT EXISTS
(
    SELECT 1 FROM dbo.Payment AS p
    INNER JOIN dbo.Booking AS b ON b.booking_id = p.booking_id
    WHERE b.booking_code = N'HTL-1002'
)
    INSERT INTO dbo.Payment (booking_id, amount)
    SELECT booking_id, 3200000
    FROM dbo.Booking WHERE booking_code = N'HTL-1002';
GO

/* Quick overview */
SELECT * FROM dbo.Guest ORDER BY guest_id;
SELECT * FROM dbo.RoomType ORDER BY type_name;
SELECT * FROM dbo.Room ORDER BY room_number;
SELECT * FROM dbo.Booking ORDER BY booking_id;
SELECT b.booking_code, b.total_amount, COALESCE(SUM(p.amount), 0) AS paid_total,
       b.total_amount - COALESCE(SUM(p.amount), 0) AS balance, b.status
FROM dbo.Booking AS b
LEFT JOIN dbo.Payment AS p ON p.booking_id = b.booking_id
GROUP BY b.booking_code, b.total_amount, b.status
ORDER BY b.booking_code;
GO
