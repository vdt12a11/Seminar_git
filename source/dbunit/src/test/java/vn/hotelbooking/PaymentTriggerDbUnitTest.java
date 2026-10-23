package vn.hotelbooking;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.sql.Statement;
import java.sql.Types;
import java.time.LocalDate;
import java.util.Arrays;
import java.util.List;

import org.dbunit.Assertion;
import org.dbunit.database.DatabaseConnection;
import org.dbunit.database.IDatabaseConnection;
import org.dbunit.dataset.ITable;
import org.dbunit.dataset.datatype.DataType;
import org.dbunit.dataset.DefaultTable;
import org.dbunit.dataset.Column;
import org.dbunit.dataset.xml.FlatXmlDataSetBuilder;
import org.dbunit.operation.DatabaseOperation;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class PaymentTriggerDbUnitTest {
    private static final String DATABASE = "hotel_booking_dbunit_demo";
    private static final String URL = System.getProperty("hotel.db.url",
            System.getenv().getOrDefault("HOTEL_DBUNIT_JDBC_URL",
                    "jdbc:sqlserver://localhost;databaseName=" + DATABASE
                            + ";encrypt=true;trustServerCertificate=true;integratedSecurity=true"));

    private Connection jdbc;
    private IDatabaseConnection dbUnit;

    @BeforeEach
    void setUp() throws Exception {
        ensureSchemaAndTrigger();
        jdbc = DriverManager.getConnection(URL);
        dbUnit = new DatabaseConnection(jdbc, "dbo");
        resetFromDbUnitFixtures();
    }

    @AfterEach
    void tearDown() throws Exception {
        if (dbUnit != null) {
            dbUnit.close();
        } else if (jdbc != null) {
            jdbc.close();
        }
    }

    @Test
    @DisplayName("TC01 — Hai đêm, không giảm: tổng 2.000.000")
    void calculatesTwoNightsWithoutDiscount() throws Exception {
        long bookingId = createBooking("2098-12-10", "2098-12-12");

        assertBooking(bookingId, 2, "0.0000", "2000000.00", "BOOKED");
        assertPayments(bookingId);
        report("TC01", "2 nights; discount 0%; total 2,000,000", "2 nights; 0%; 2,000,000; BOOKED");
    }

    @Test
    @DisplayName("TC02 — Ba đêm, giảm 10%: tổng 2.700.000")
    void calculatesThreeNightsWithDiscount() throws Exception {
        long bookingId = createBooking("2098-12-10", "2098-12-13");

        assertBooking(bookingId, 3, "0.1000", "2700000.00", "BOOKED");
        assertPayments(bookingId);
        report("TC02", "3 nights; discount 10%; total 2,700,000", "3 nights; 10%; 2,700,000; BOOKED");
    }

    @Test
    @DisplayName("TC03 — Thanh toán một phần: vẫn BOOKED")
    void partialPaymentKeepsBookingBooked() throws Exception {
        long bookingId = createBooking("2098-12-10", "2098-12-13");
        insertPayment(bookingId, "2000000.00");

        assertBooking(bookingId, 3, "0.1000", "2700000.00", "BOOKED");
        assertPayments(bookingId, "2000000.00");
        report("TC03", "Paid 2,000,000; status BOOKED", "Paid 2,000,000; BOOKED");
    }

    @Test
    @DisplayName("TC04 — Thanh toán đủ: trigger chuyển sang PAID")
    void fullPaymentSetsPaid() throws Exception {
        long bookingId = createBooking("2098-12-10", "2098-12-13");
        insertPayment(bookingId, "2000000.00");
        assertBooking(bookingId, 3, "0.1000", "2700000.00", "BOOKED");
        insertPayment(bookingId, "700000.00");

        assertBooking(bookingId, 3, "0.1000", "2700000.00", "PAID");
        assertPayments(bookingId, "2000000.00", "700000.00");
        report("TC04", "Paid total 2,700,000; status PAID", "Paid total 2,700,000; PAID");
    }

    @Test
    @DisplayName("TC05 — Giảm tổng payment: trigger trả booking về BOOKED")
    void reducingPaymentReturnsBookingToBooked() throws Exception {
        long bookingId = createBooking("2098-12-10", "2098-12-13");
        insertPayment(bookingId, "2000000.00");
        insertPayment(bookingId, "700000.00");
        updatePayment(bookingId, "2000000.00", "1500000.00");

        assertBooking(bookingId, 3, "0.1000", "2700000.00", "BOOKED");
        assertPayments(bookingId, "1500000.00", "700000.00");
        report("TC05", "Paid total 2,200,000; status BOOKED", "Paid total 2,200,000; BOOKED");
    }

    @Test
    @DisplayName("TC06 — Xóa payment: tính lại tổng và trạng thái")
    void deletingPaymentsRecalculatesStatus() throws Exception {
        long bookingId = createBooking("2098-12-10", "2098-12-13");
        insertPayment(bookingId, "2000000.00");
        insertPayment(bookingId, "700000.00");
        deletePayments(bookingId, 2);

        assertBooking(bookingId, 3, "0.1000", "2700000.00", "BOOKED");
        assertPayments(bookingId);
        report("TC06", "Paid total 0; status BOOKED", "Paid total 0; BOOKED");
    }

    @Test
    @DisplayName("TC07 — CANCELLED: thêm payment không đổi trạng thái")
    void cancelledBookingStaysCancelledAfterInsert() throws Exception {
        long bookingId = cancelledBooking();
        insertPayment(bookingId, "100000.00");

        assertBooking(bookingId, 3, "0.1000", "2700000.00", "CANCELLED");
        assertPayments(bookingId, "100000.00");
        report("TC07", "CANCELLED remains CANCELLED after insert", "CANCELLED");
    }

    @Test
    @DisplayName("TC08 — CANCELLED: sửa payment không đổi trạng thái")
    void cancelledBookingStaysCancelledAfterUpdate() throws Exception {
        long bookingId = cancelledBooking();
        insertPayment(bookingId, "100000.00");
        updatePayment(bookingId, "100000.00", "200000.00");

        assertBooking(bookingId, 3, "0.1000", "2700000.00", "CANCELLED");
        assertPayments(bookingId, "200000.00");
        report("TC08", "CANCELLED remains CANCELLED after update", "CANCELLED");
    }

    @Test
    @DisplayName("TC09 — CANCELLED: xóa payment không đổi trạng thái")
    void cancelledBookingStaysCancelledAfterDelete() throws Exception {
        long bookingId = cancelledBooking();
        insertPayment(bookingId, "100000.00");
        deletePayments(bookingId, 1);

        assertBooking(bookingId, 3, "0.1000", "2700000.00", "CANCELLED");
        assertPayments(bookingId);
        report("TC09", "Paid total 0; status remains CANCELLED", "CANCELLED");
    }

    private long createBooking(String checkIn, String checkOut) throws SQLException {
        try (CallableStatement call = jdbc.prepareCall("{call dbo.create_booking(?, ?, ?, ?, ?, ?)}")) {
            call.setLong(1, 1);
            call.setLong(2, 1);
            call.setDate(3, java.sql.Date.valueOf(LocalDate.parse(checkIn)));
            call.setDate(4, java.sql.Date.valueOf(LocalDate.parse(checkOut)));
            call.setBigDecimal(5, java.math.BigDecimal.ZERO);
            call.registerOutParameter(6, Types.BIGINT);
            call.execute();
            return call.getLong(6);
        }
    }

    private long cancelledBooking() throws SQLException {
        long bookingId = createBooking("2098-12-10", "2098-12-13");
        try (PreparedStatement update = jdbc.prepareStatement(
                "UPDATE dbo.Booking SET status='CANCELLED' WHERE booking_id=?")) {
            update.setLong(1, bookingId);
            assertEquals(1, update.executeUpdate());
        }
        return bookingId;
    }

    private void insertPayment(long bookingId, String amount) throws SQLException {
        try (PreparedStatement insert = jdbc.prepareStatement(
                "INSERT dbo.Payment(booking_id, amount) VALUES (?, ?)")) {
            insert.setLong(1, bookingId);
            insert.setBigDecimal(2, new java.math.BigDecimal(amount));
            insert.executeUpdate();
        }
    }

    private void updatePayment(long bookingId, String oldAmount, String newAmount) throws SQLException {
        try (PreparedStatement update = jdbc.prepareStatement(
                "UPDATE dbo.Payment SET amount=? WHERE booking_id=? AND amount=?")) {
            update.setBigDecimal(1, new java.math.BigDecimal(newAmount));
            update.setLong(2, bookingId);
            update.setBigDecimal(3, new java.math.BigDecimal(oldAmount));
            assertEquals(1, update.executeUpdate());
        }
    }

    private void deletePayments(long bookingId, int expectedRows) throws SQLException {
        try (PreparedStatement delete = jdbc.prepareStatement("DELETE dbo.Payment WHERE booking_id=?")) {
            delete.setLong(1, bookingId);
            assertEquals(expectedRows, delete.executeUpdate());
        }
    }

    private void assertBooking(long bookingId, int nights, String discount, String total, String status)
            throws Exception {
        DefaultTable expected = new DefaultTable("Booking", new Column[] {
                new Column("booking_id", DataType.BIGINT), new Column("nights", DataType.INTEGER),
                new Column("discount_rate", DataType.DECIMAL), new Column("total_amount", DataType.DECIMAL),
                new Column("status", DataType.VARCHAR)
        });
        expected.addRow(new Object[] { bookingId, nights, new java.math.BigDecimal(discount),
                new java.math.BigDecimal(total), status });
        ITable actual = dbUnit.createQueryTable("Booking", "SELECT booking_id, nights, discount_rate, total_amount, status "
                + "FROM dbo.Booking WHERE booking_id=" + bookingId);
        Assertion.assertEquals(expected, actual);
    }

    private void assertPayments(long bookingId, String... amounts) throws Exception {
        DefaultTable expected = new DefaultTable("Payment", new Column[] {
                new Column("booking_id", DataType.BIGINT), new Column("amount", DataType.DECIMAL)
        });
        for (String amount : Arrays.stream(amounts)
                .sorted(java.util.Comparator.comparing(java.math.BigDecimal::new)).toList()) {
            expected.addRow(new Object[] { bookingId, new java.math.BigDecimal(amount) });
        }
        ITable actual = dbUnit.createQueryTable("Payment", "SELECT booking_id, amount FROM dbo.Payment "
                + "WHERE booking_id=" + bookingId + " ORDER BY amount");
        Assertion.assertEquals(expected, actual);
    }

    private void report(String tc, String expected, String actual) {
        System.out.println(tc + " | EXPECT: " + expected);
        System.out.println(tc + " | ACTUAL: " + actual);
        System.out.println(tc + " | DBUnit: Booking and Payment rows match expected values");
    }

    private void resetFromDbUnitFixtures() throws Exception {
        for (String table : List.of("Payment", "Booking", "Guest", "Room")) {
            DatabaseOperation.DELETE_ALL.execute(dbUnit, xmlDataSet("/datasets/" + table + ".xml"));
        }
        for (String table : List.of("Guest", "Room", "Booking", "Payment")) {
            try (Statement statement = jdbc.createStatement()) {
                statement.execute("SET IDENTITY_INSERT dbo." + table + " ON");
            }
            try {
                DatabaseOperation.INSERT.execute(dbUnit, xmlDataSet("/datasets/" + table + ".xml"));
            } finally {
                try (Statement statement = jdbc.createStatement()) {
                    statement.execute("SET IDENTITY_INSERT dbo." + table + " OFF");
                }
            }
        }
        try (Statement statement = jdbc.createStatement()) {
            statement.execute("DBCC CHECKIDENT ('dbo.Booking', RESEED, 101)");
        }
    }

    private org.dbunit.dataset.IDataSet xmlDataSet(String resource) throws Exception {
        try (InputStream input = getClass().getResourceAsStream(resource)) {
            assertNotNull(input, "Missing DBUnit dataset resource: " + resource);
            return new FlatXmlDataSetBuilder().build(input);
        }
    }

    private void ensureSchemaAndTrigger() throws Exception {
        String masterUrl = URL.replace("databaseName=" + DATABASE, "databaseName=master");
        try (Connection master = DriverManager.getConnection(masterUrl);
             Statement statement = master.createStatement()) {
            statement.execute("IF DB_ID(N'" + DATABASE + "') IS NULL CREATE DATABASE " + DATABASE);
        }
        try (Connection target = DriverManager.getConnection(URL);
             Statement statement = target.createStatement();
             var result = statement.executeQuery("SELECT OBJECT_ID(N'dbo.trg_Payment_UpdateBookingStatus', N'TR')")) {
            result.next();
            if (result.getObject(1) != null) {
                return;
            }
        }
        String schema = readResource("/sql/hotel_booking_schema.sql");
        List<String> batches = Arrays.stream(schema.split("(?im)^\\s*GO\\s*(?:--.*)?$"))
                .map(String::trim).filter(batch -> !batch.isEmpty()).toList();
        try (Connection target = DriverManager.getConnection(URL); Statement statement = target.createStatement()) {
            for (int i = 2; i < batches.size(); i++) {
                statement.execute(batches.get(i));
            }
        }
    }

    private String readResource(String resource) throws IOException {
        try (InputStream input = getClass().getResourceAsStream(resource)) {
            if (input == null) {
                throw new IOException("Missing schema resource: " + resource);
            }
            return new String(input.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
}
