package vn.hotelbooking;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.InputStream;
import java.math.BigDecimal;
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
import java.util.Comparator;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import org.dbunit.Assertion;
import org.dbunit.database.DatabaseConnection;
import org.dbunit.database.IDatabaseConnection;
import org.dbunit.dataset.Column;
import org.dbunit.dataset.DefaultTable;
import org.dbunit.dataset.ITable;
import org.dbunit.dataset.datatype.DataType;
import org.dbunit.dataset.xml.FlatXmlDataSetBuilder;
import org.dbunit.operation.DatabaseOperation;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * Item 5 checks against the objects present in the supplied SQL schema.
 * Uses a demo payment procedure with an intentional overpayment defect.
 */
class PaymentItem5DbUnitTest {
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
    @DisplayName("TC01 — Thanh toán chia lần đủ 2.700.000: chuyển sang PAID")
    void splitPaymentsSetBookingPaid() throws Exception {
        long bookingId = createBooking();

        recordPayment(jdbc, bookingId, "2000000.00");
        assertBooking(bookingId, "2700000.00", "BOOKED");
        assertPayments(bookingId, "2000000.00");

        recordPayment(jdbc, bookingId, "700000.00");

        assertBooking(bookingId, "2700000.00", "PAID");
        assertPayments(bookingId, "2000000.00", "700000.00");
        report("TC01", "2,700,000 paid in two calls; booking PAID",
                "2,700,000 paid; booking PAID");
    }

    @Test
    @DisplayName("TC02 — Vượt số dư: lần ghi lỗi không làm đổi dữ liệu")
    void overpaymentRollsBackTheAttemptedPayment() throws Exception {
        long bookingId = createBooking();
        recordPayment(jdbc, bookingId, "2000000.00");
        SQLException error = null;
        try {
            recordPayment(jdbc, bookingId, "800000.00");
        } catch (SQLException rejected) {
            error = rejected;
        }
        System.out.println("TC02 | EXPECT: 800,000 rejected; paid=2,000,000; BOOKED");
        System.out.println("TC02 | ACTUAL: error=" + (error == null ? "none" : error.getErrorCode())
                + "; paid=" + paidTotal(bookingId) + "; status=" + bookingStatus(bookingId));
        assertNotNull(error, "Payment above 2,700,000 must be rejected");
        assertBooking(bookingId, "2700000.00", "BOOKED");
        assertPayments(bookingId, "2000000.00");
    }

    @Test
    @DisplayName("TC03 — Hai connection thanh toán đồng thời: tổng không vượt 2.700.000")
    void concurrentPaymentsCannotExceedBookingTotal() throws Exception {
        long bookingId = createBooking();
        recordPayment(jdbc, bookingId, "2000000.00");
        CountDownLatch ready = new CountDownLatch(2);
        CountDownLatch start = new CountDownLatch(1);
        ExecutorService pool = Executors.newFixedThreadPool(2);
        try {
            Future<Boolean> first = pool.submit(() -> concurrentPayment(bookingId, ready, start));
            Future<Boolean> second = pool.submit(() -> concurrentPayment(bookingId, ready, start));
            assertTrue(ready.await(15, TimeUnit.SECONDS));
            start.countDown();
            int accepted = (first.get(30, TimeUnit.SECONDS) ? 1 : 0)
                    + (second.get(30, TimeUnit.SECONDS) ? 1 : 0);
            System.out.println("TC03 | EXPECT: one 600,000 payment accepted; paid=2,600,000; BOOKED");
            System.out.println("TC03 | ACTUAL: accepted=" + accepted + "; paid=" + paidTotal(bookingId)
                    + "; status=" + bookingStatus(bookingId));
            assertEquals(1, accepted);
            assertBooking(bookingId, "2700000.00", "BOOKED");
            assertPayments(bookingId, "2000000.00", "600000.00");
        } finally {
            start.countDown();
            pool.shutdownNow();
        }
    }

    private boolean concurrentPayment(long bookingId, CountDownLatch ready, CountDownLatch start) throws Exception {
        try (Connection connection = DriverManager.getConnection(URL)) {
            ready.countDown();
            assertTrue(start.await(15, TimeUnit.SECONDS));
            try {
                recordPayment(connection, bookingId, "600000.00");
                return true;
            } catch (SQLException error) {
                assertEquals(50007, error.getErrorCode());
                return false;
            }
        }
    }

    private long createBooking() throws SQLException {
        try (CallableStatement call = jdbc.prepareCall("{call dbo.create_booking(?, ?, ?, ?, ?, ?)}")) {
            call.setLong(1, 1);
            call.setLong(2, 1);
            call.setDate(3, java.sql.Date.valueOf(LocalDate.parse("2098-12-10")));
            call.setDate(4, java.sql.Date.valueOf(LocalDate.parse("2098-12-13")));
            call.setBigDecimal(5, BigDecimal.ZERO);
            call.registerOutParameter(6, Types.BIGINT);
            call.execute();
            return call.getLong(6);
        }
    }

    private void recordPayment(Connection connection, long bookingId, String amount) throws SQLException {
        try (CallableStatement call = connection.prepareCall("{call dbo.record_booking_payment(?, ?)}")) {
            call.setLong(1, bookingId);
            call.setBigDecimal(2, new BigDecimal(amount));
            call.execute();
        }
    }

    private BigDecimal paidTotal(long bookingId) throws SQLException {
        try (Statement query = jdbc.createStatement();
             var rows = query.executeQuery("SELECT COALESCE(SUM(amount),0) FROM dbo.Payment WHERE booking_id=" + bookingId)) {
            rows.next();
            return rows.getBigDecimal(1);
        }
    }

    private String bookingStatus(long bookingId) throws SQLException {
        try (Statement query = jdbc.createStatement();
             var rows = query.executeQuery("SELECT status FROM dbo.Booking WHERE booking_id=" + bookingId)) {
            rows.next();
            return rows.getString(1);
        }
    }

    private void assertBooking(long bookingId, String total, String status) throws Exception {
        DefaultTable expected = new DefaultTable("Booking", new Column[] {
                new Column("booking_id", DataType.BIGINT),
                new Column("total_amount", DataType.DECIMAL),
                new Column("status", DataType.VARCHAR)
        });
        expected.addRow(new Object[] { bookingId, new BigDecimal(total), status });
        ITable actual = dbUnit.createQueryTable("Booking",
                "SELECT booking_id, total_amount, status FROM dbo.Booking WHERE booking_id=" + bookingId);
        Assertion.assertEquals(expected, actual);
    }

    private void assertPayments(long bookingId, String... amounts) throws Exception {
        DefaultTable expected = new DefaultTable("Payment", new Column[] {
                new Column("booking_id", DataType.BIGINT), new Column("amount", DataType.DECIMAL)
        });
        List<String> sortedAmounts = Arrays.stream(amounts)
                .sorted(Comparator.comparing(BigDecimal::new)).toList();
        for (String amount : sortedAmounts) {
            expected.addRow(new Object[] { bookingId, new BigDecimal(amount) });
        }
        ITable actual = dbUnit.createQueryTable("Payment",
                "SELECT booking_id, amount FROM dbo.Payment WHERE booking_id=" + bookingId + " ORDER BY amount");
        Assertion.assertEquals(expected, actual);
    }

    private void report(String caseId, String expected, String actual) {
        System.out.println(caseId + " | EXPECT: " + expected);
        System.out.println(caseId + " | ACTUAL: " + actual);
        System.out.println(caseId + " | DBUnit: Booking and Payment rows match expected values");
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
        boolean initialized;
        try (Connection target = DriverManager.getConnection(URL);
             Statement statement = target.createStatement();
             var result = statement.executeQuery("SELECT OBJECT_ID(N'dbo.trg_Payment_UpdateBookingStatus', N'TR')")) {
            result.next();
            initialized = result.getObject(1) != null;
        }
        String schema = readResource("/sql/hotel_booking_schema.sql");
        List<String> batches = Arrays.stream(schema.split("(?im)^\\s*GO\\s*(?:--.*)?$"))
                .map(String::trim).filter(batch -> !batch.isEmpty()).toList();
        try (Connection target = DriverManager.getConnection(URL); Statement statement = target.createStatement()) {
            for (int i = 2; i < batches.size(); i++) {
                String batch = batches.get(i);
                if (!initialized || batch.contains("CREATE OR ALTER PROCEDURE dbo.record_booking_payment")) {
                    statement.execute(batch);
                }
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
