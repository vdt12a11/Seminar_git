package vn.hotelbooking;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.sql.Statement;
import java.sql.Types;
import java.time.LocalDate;
import java.util.Arrays;
import java.util.List;

import org.dbunit.Assertion;
import org.dbunit.database.DatabaseConnection;
import org.dbunit.database.IDatabaseConnection;
import org.dbunit.dataset.IDataSet;
import org.dbunit.dataset.ITable;
import org.dbunit.dataset.SortedTable;
import org.dbunit.dataset.filter.DefaultColumnFilter;
import org.dbunit.dataset.xml.FlatXmlDataSetBuilder;
import org.dbunit.operation.DatabaseOperation;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class BookingProcedureDbUnitTest {
    private static final String DATABASE = "hotel_booking_dbunit_demo";
    private static final String URL = System.getProperty("hotel.db.url",
            System.getenv().getOrDefault("HOTEL_DBUNIT_JDBC_URL",
                    "jdbc:sqlserver://localhost;databaseName=" + DATABASE
                            + ";encrypt=true;trustServerCertificate=true;integratedSecurity=true"));

    private Connection jdbc;
    private IDatabaseConnection dbUnit;

    @BeforeEach
    void setUp() throws Exception {
        ensureDatabaseAndProcedure();
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
    @DisplayName("TC01 — Chồng lấn một phần 11–13: phải từ chối")
    void rejectsPartialOverlap() throws Exception {
        SQLException error = assertThrows(SQLException.class,
                () -> createBooking(1, 1, "2026-11-11", "2026-11-13"));

        assertOverlapRejection(error);
        assertBookingTableMatches("/datasets/Booking.xml");
        report("TC01", "REJECT; preserve seed bookings 100 and 101", "REJECT: " + error.getMessage());
    }

    @Test
    @DisplayName("TC02 — Chồng lấn đầu kỳ 09–11: phải từ chối")
    void rejectsOverlapAtStart() throws Exception {
        SQLException error = assertThrows(SQLException.class,
                () -> createBooking(1, 1, "2026-11-09", "2026-11-11"));

        assertOverlapRejection(error);
        assertBookingTableMatches("/datasets/Booking.xml");
        report("TC02", "REJECT; preserve seed bookings 100 and 101", "REJECT: " + error.getMessage());
    }

    @Test
    @DisplayName("TC03 — Trùng hoàn toàn 10–12: phải từ chối")
    void rejectsExactOverlap() throws Exception {
        SQLException error = assertThrows(SQLException.class,
                () -> createBooking(1, 1, "2026-11-10", "2026-11-12"));

        assertOverlapRejection(error);
        assertBookingTableMatches("/datasets/Booking.xml");
        report("TC03", "REJECT; preserve seed bookings 100 and 101", "REJECT: " + error.getMessage());
    }

    @Test
    @DisplayName("TC04 — Nhận phòng đúng ngày checkout 12–14: chấp nhận")
    void acceptsAdjacentCheckout() throws Exception {
        long bookingId = createBooking(1, 1, "2026-11-12", "2026-11-14");

        assertEquals(102L, bookingId, "The new booking should be returned by the OUTPUT parameter");
        assertBookingTableMatches("/expected/Booking-adjacent.xml");
        report("TC04", "ACCEPT; booking 102 for room 101, 12-14 Nov, BOOKED",
                "ACCEPT; booking_id=" + bookingId);
    }

    @Test
    @DisplayName("TC05 — Cùng ngày ở phòng khác: chấp nhận")
    void acceptsSameDatesForAnotherRoom() throws Exception {
        // Booking 101 is an unrelated fixture that already occupies room 201 on these dates.
        // Remove it so this test matches the stated precondition: only room 101 is booked.
        try (Statement statement = jdbc.createStatement()) {
            statement.executeUpdate("DELETE FROM dbo.Booking WHERE booking_id=101");
        }

        long bookingId = createBooking(1, 2, "2026-11-10", "2026-11-12");

        assertEquals(102L, bookingId, "The new booking should be returned by the OUTPUT parameter");
        assertBookingTableMatches("/expected/Booking-other-room.xml");
        report("TC05", "ACCEPT; booking 100 room 101 and booking 102 room 201 on the same dates",
                "ACCEPT; booking_id=" + bookingId);
    }

    @Test
    @DisplayName("TC06 — Đặt lại ngày sau khi booking cũ CANCELLED: chấp nhận")
    void acceptsDatesReleasedByCancelledBooking() throws Exception {
        try (Statement statement = jdbc.createStatement()) {
            assertEquals(1, statement.executeUpdate(
                    "UPDATE dbo.Booking SET status='CANCELLED' WHERE booking_id=100"));
        }

        long bookingId = createBooking(1, 1, "2026-11-10", "2026-11-12");

        assertEquals(102L, bookingId, "The new booking should be returned by the OUTPUT parameter");
        assertBookingTableMatches("/expected/Booking-cancelled-reuse.xml");
        report("TC06", "ACCEPT; old booking CANCELLED, new booking 102 BOOKED",
                "ACCEPT; booking_id=" + bookingId);
    }

    private long createBooking(long guestId, long roomId, String checkIn, String checkOut) throws SQLException {
        try (CallableStatement call = jdbc.prepareCall("{call dbo.create_booking(?, ?, ?, ?, ?, ?)}")) {
            call.setLong(1, guestId);
            call.setLong(2, roomId);
            call.setDate(3, java.sql.Date.valueOf(LocalDate.parse(checkIn)));
            call.setDate(4, java.sql.Date.valueOf(LocalDate.parse(checkOut)));
            call.setBigDecimal(5, java.math.BigDecimal.ZERO);
            call.registerOutParameter(6, Types.BIGINT);
            call.execute();
            return call.getLong(6);
        }
    }

    private void assertOverlapRejection(SQLException error) {
        assertTrue(error.getMessage().contains("Room is already booked for these dates."),
                "Expected the overlap rule's SQL error, actual: " + error.getMessage());
    }

    private void assertBookingTableMatches(String expectedResource) throws Exception {
        IDataSet expectedDataSet = xmlDataSet(expectedResource);
        IDataSet actualDataSet = dbUnit.createDataSet(new String[] { "Booking" });
        ITable expected = expectedDataSet.getTable("Booking");
        ITable actual = DefaultColumnFilter.includedColumnsTable(
                actualDataSet.getTable("Booking"), expected.getTableMetaData().getColumns());
        Assertion.assertEquals(new SortedTable(expected, new String[] { "booking_id" }),
                new SortedTable(actual, new String[] { "booking_id" }));
        System.out.println("DbUnit: Booking table matches expected XML " + expectedResource);
    }

    private void report(String caseId, String expected, String actual) throws SQLException {
        System.out.println(caseId + " | EXPECT: " + expected);
        System.out.println(caseId + " | ACTUAL: " + actual);
        try (Statement statement = jdbc.createStatement();
             var rows = statement.executeQuery(
                     "SELECT b.booking_id, r.room_number, b.check_in, b.check_out, b.nights, "
                             + "b.total_amount, b.status FROM dbo.Booking b "
                             + "JOIN dbo.Room r ON r.room_id=b.room_id ORDER BY b.booking_id")) {
            while (rows.next()) {
                System.out.printf("Booking row: id=%d room=%s %s..%s nights=%d total=%s status=%s%n",
                        rows.getLong("booking_id"), rows.getString("room_number"),
                        rows.getDate("check_in"), rows.getDate("check_out"),
                        rows.getInt("nights"), rows.getBigDecimal("total_amount"),
                        rows.getString("status"));
            }
        }
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

    private IDataSet xmlDataSet(String resource) throws Exception {
        try (InputStream input = getClass().getResourceAsStream(resource)) {
            assertNotNull(input, "Missing DBUnit dataset resource: " + resource);
            return new FlatXmlDataSetBuilder().build(input);
        }
    }

    private void ensureDatabaseAndProcedure() throws Exception {
        String masterUrl = URL.replace("databaseName=" + DATABASE, "databaseName=master");
        try (Connection master = DriverManager.getConnection(masterUrl);
             Statement statement = master.createStatement()) {
            statement.execute("IF DB_ID(N'" + DATABASE + "') IS NULL CREATE DATABASE " + DATABASE);
        }

        try (Connection target = DriverManager.getConnection(URL);
             Statement statement = target.createStatement()) {
            try (var result = statement.executeQuery("SELECT OBJECT_ID(N'dbo.create_booking', N'P')")) {
                result.next();
                if (result.getObject(1) != null) {
                    return;
                }
            }

            String schema = readResource("/sql/hotel_booking_schema.sql");
            List<String> batches = Arrays.stream(schema.split("(?im)^\\s*GO\\s*(?:--.*)?$"))
                    .map(String::trim)
                    .filter(batch -> !batch.isEmpty())
                    .toList();
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
