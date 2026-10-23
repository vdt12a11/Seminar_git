package vn.hotelbooking;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.InputStream;
import java.math.BigDecimal;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.sql.Types;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

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

/**
 * Demo for req.md: (1) keys and constraints, (2) CRUD and business rules.
 * Requires the schema from sql/hotel_booking_dbunit_schema.sql to exist already.
 * Connection: -Dhotel.db.url=... or env HOTEL_DBUNIT_JDBC_URL (use SQL authentication).
 */
class ConstraintAndCrudDbUnitTest {
    private static final String DATABASE = System.getProperty("hotel.db.name", "hotel_booking_dbunit_demo");
    private static final String URL = System.getProperty("hotel.db.url",
            System.getenv().getOrDefault("HOTEL_DBUNIT_JDBC_URL",
                    "jdbc:sqlserver://localhost:1433;databaseName=" + DATABASE
                            + ";encrypt=true;trustServerCertificate=true;user=demo;password=Demo@12345"));

    private static final int FK_OR_CHECK_VIOLATION = 547;
    private static final int UNIQUE_VIOLATION = 2627;

    private Connection jdbc;
    private IDatabaseConnection dbUnit;

    @BeforeEach
    void setUp() throws Exception {
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

    // ===================== Part 1: keys and constraints =====================

    @Test
    @DisplayName("1.1 PK — Guest, Room, Booking, Payment have PK on the right column")
    void primaryKeysExistOnCorrectColumns() throws Exception {
        Map<String, String> actual = new TreeMap<>();
        String sql = "SELECT t.name AS tbl, c.name AS col FROM sys.indexes i "
                + "JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id "
                + "JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id "
                + "JOIN sys.tables t ON t.object_id=i.object_id WHERE i.is_primary_key=1";
        try (Statement st = jdbc.createStatement(); ResultSet rs = st.executeQuery(sql)) {
            while (rs.next()) {
                actual.put(rs.getString("tbl"), rs.getString("col"));
            }
        }
        assertEquals(Map.of("Guest", "guest_id", "Room", "room_id",
                "Booking", "booking_id", "Payment", "payment_id"), actual);
        System.out.println("1.1 PK map: " + actual);
    }

    @Test
    @DisplayName("1.2 FK — booking with missing guest is rejected")
    void rejectsBookingWithMissingGuest() throws Exception {
        SQLException e = assertThrows(SQLException.class, () -> exec(
                "INSERT dbo.Booking(guest_id,room_id,check_in,check_out,nights,total_amount) "
                        + "VALUES (999,1,'2027-01-01','2027-01-02',1,1000000)"));
        assertEquals(FK_OR_CHECK_VIOLATION, e.getErrorCode());
        assertTrue(e.getMessage().contains("FK_Booking_Guest"), e.getMessage());
        assertBookingTableUnchanged();
    }

    @Test
    @DisplayName("1.2 FK — booking with missing room is rejected")
    void rejectsBookingWithMissingRoom() throws Exception {
        SQLException e = assertThrows(SQLException.class, () -> exec(
                "INSERT dbo.Booking(guest_id,room_id,check_in,check_out,nights,total_amount) "
                        + "VALUES (1,999,'2027-01-01','2027-01-02',1,1000000)"));
        assertEquals(FK_OR_CHECK_VIOLATION, e.getErrorCode());
        assertTrue(e.getMessage().contains("FK_Booking_Room"), e.getMessage());
        assertBookingTableUnchanged();
    }

    @Test
    @DisplayName("1.2 FK — payment with missing booking is rejected")
    void rejectsPaymentWithMissingBooking() throws Exception {
        SQLException e = assertThrows(SQLException.class, () -> exec(
                "INSERT dbo.Payment(booking_id,amount) VALUES (999,100000)"));
        assertEquals(FK_OR_CHECK_VIOLATION, e.getErrorCode());
        assertTrue(e.getMessage().contains("FK_Payment_Booking"), e.getMessage());
        assertTableMatches("Payment", "/datasets/Payment.xml", "payment_id");
    }

    @Test
    @DisplayName("1.5 Delete referenced guest is rejected")
    void deleteGuestWithBookingRejected() throws Exception {
        SQLException e = assertThrows(SQLException.class, () -> exec("DELETE FROM dbo.Guest WHERE guest_id=1"));
        assertEquals(FK_OR_CHECK_VIOLATION, e.getErrorCode());
        assertTableMatches("Guest", "/datasets/Guest.xml", "guest_id");
    }

    @Test
    @DisplayName("1.5 Delete referenced room is rejected")
    void deleteRoomWithBookingRejected() throws Exception {
        SQLException e = assertThrows(SQLException.class, () -> exec("DELETE FROM dbo.Room WHERE room_id=1"));
        assertEquals(FK_OR_CHECK_VIOLATION, e.getErrorCode());
        assertTableMatches("Room", "/datasets/Room.xml", "room_id");
    }

    @Test
    @DisplayName("1.5 Delete booking cascades to its payments")
    void deleteBookingCascadesPayment() throws Exception {
        assertEquals(1, exec("DELETE FROM dbo.Booking WHERE booking_id=100"));
        assertTableMatches("Payment", "/expected/Payment-after-cascade.xml", "payment_id");
    }

    // ===================== Part 2: CRUD and business rules =====================

    @Test
    @DisplayName("2.1 Create valid booking returns booking ID")
    void createBookingValid() throws Exception {
        Long id = createBooking(1, 2, "2026-12-01", "2026-12-04", "0");
        assertNotNull(id);
        assertEquals(102L, id);
        try (Statement st = jdbc.createStatement();
             ResultSet rs = st.executeQuery("SELECT nights, discount_rate, total_amount, status "
                     + "FROM dbo.Booking WHERE booking_id=" + id)) {
            assertTrue(rs.next());
            assertEquals(3, rs.getInt("nights"));
            assertEquals(0, new BigDecimal("0.1000").compareTo(rs.getBigDecimal("discount_rate")));
            assertEquals(0, new BigDecimal("4050000.00").compareTo(rs.getBigDecimal("total_amount")));
            assertEquals("BOOKED", rs.getString("status"));
        }
    }

    @Test
    @DisplayName("2.2 Read booking and payment match expected data")
    void readBookingAndPayment() throws Exception {
        assertTableMatches("Booking", "/datasets/Booking.xml", "booking_id");
        assertTableMatches("Payment", "/datasets/Payment.xml", "payment_id");
    }

    @Test
    @DisplayName("2.3 Update email OK; duplicate email and non-positive price rejected")
    void updateDataAndConstraintsStillApply() throws Exception {
        assertEquals(1, exec("UPDATE dbo.Guest SET email='an.new@example.test' WHERE guest_id=1"));
        assertEquals("an.new@example.test", queryString("SELECT email FROM dbo.Guest WHERE guest_id=1"));

        SQLException dup = assertThrows(SQLException.class,
                () -> exec("UPDATE dbo.Guest SET email='binh.tran@example.test' WHERE guest_id=1"));
        assertEquals(UNIQUE_VIOLATION, dup.getErrorCode());

        assertEquals(1, exec("UPDATE dbo.Room SET price_per_night=1200000 WHERE room_id=1"));
        SQLException price = assertThrows(SQLException.class,
                () -> exec("UPDATE dbo.Room SET price_per_night=0 WHERE room_id=1"));
        assertEquals(FK_OR_CHECK_VIOLATION, price.getErrorCode());
        assertEquals("1200000.00", queryString("SELECT CONVERT(VARCHAR(20),price_per_night) FROM dbo.Room WHERE room_id=1"));
    }

    @Test
    @DisplayName("2.4 Delete payment: trigger moves booking PAID -> BOOKED")
    void deletePaymentUpdatesBookingStatus() throws Exception {
        // Booking 100 total = 2,000,000; seed payment 500,000. Add 1,500,000 -> fully paid.
        exec("INSERT dbo.Payment(booking_id, amount) VALUES (100, 1500000)");
        assertEquals("PAID", queryString("SELECT status FROM dbo.Booking WHERE booking_id=100"));

        assertEquals(1, exec("DELETE FROM dbo.Payment WHERE payment_id=1000"));
        assertEquals("BOOKED", queryString("SELECT status FROM dbo.Booking WHERE booking_id=100"));
    }

    @Test
    @DisplayName("2.5 Checkout <= check-in is rejected, no booking created")
    void invalidDatesRejected() throws Exception {
        for (String[] range : new String[][] { { "2026-12-05", "2026-12-05" }, { "2026-12-05", "2026-12-03" } }) {
            SQLException e = assertThrows(SQLException.class,
                    () -> createBooking(1, 2, range[0], range[1], "0"));
            assertTrue(e.getMessage().contains("Invalid booking date range."), e.getMessage());
        }
        assertBookingTableUnchanged();
    }

    @Test
    @DisplayName("2.8 Invalid initial payment (negative or above total) is rejected")
    void invalidInitialPaymentRejected() throws Exception {
        // Room 2, 3 nights => total 4,050,000
        for (String amount : List.of("-1", "5000000")) {
            SQLException e = assertThrows(SQLException.class,
                    () -> createBooking(1, 2, "2026-12-01", "2026-12-04", amount));
            assertTrue(e.getMessage().contains("Initial payment must be between zero and booking total."),
                    e.getMessage());
        }
        assertBookingTableUnchanged();
        assertTableMatches("Payment", "/datasets/Payment.xml", "payment_id");
    }

    // ===================== helpers =====================

    private int exec(String sql) throws SQLException {
        try (Statement st = jdbc.createStatement()) {
            return st.executeUpdate(sql);
        }
    }

    private String queryString(String sql) throws SQLException {
        try (Statement st = jdbc.createStatement(); ResultSet rs = st.executeQuery(sql)) {
            assertTrue(rs.next());
            return rs.getString(1);
        }
    }

    private Long createBooking(long guestId, long roomId, String checkIn, String checkOut, String payment)
            throws SQLException {
        try (CallableStatement call = jdbc.prepareCall("{call dbo.create_booking(?, ?, ?, ?, ?, ?)}")) {
            call.setLong(1, guestId);
            call.setLong(2, roomId);
            call.setDate(3, java.sql.Date.valueOf(LocalDate.parse(checkIn)));
            call.setDate(4, java.sql.Date.valueOf(LocalDate.parse(checkOut)));
            call.setBigDecimal(5, new BigDecimal(payment));
            call.registerOutParameter(6, Types.BIGINT);
            call.execute();
            long id = call.getLong(6);
            return call.wasNull() ? null : id;
        }
    }

    private void assertBookingTableUnchanged() throws Exception {
        assertTableMatches("Booking", "/datasets/Booking.xml", "booking_id");
    }

    private void assertTableMatches(String table, String expectedResource, String sortColumn) throws Exception {
        ITable expected = xmlDataSet(expectedResource).getTable(table);
        ITable actual = DefaultColumnFilter.includedColumnsTable(
                dbUnit.createDataSet(new String[] { table }).getTable(table),
                expected.getTableMetaData().getColumns());
        Assertion.assertEquals(new SortedTable(expected, new String[] { sortColumn }),
                new SortedTable(actual, new String[] { sortColumn }));
        System.out.println("DbUnit: " + table + " matches " + expectedResource);
    }

    private void resetFromDbUnitFixtures() throws Exception {
        for (String table : List.of("Payment", "Booking", "Guest", "Room")) {
            DatabaseOperation.DELETE_ALL.execute(dbUnit, xmlDataSet("/datasets/" + table + ".xml"));
        }
        for (String table : List.of("Guest", "Room", "Booking", "Payment")) {
            exec("SET IDENTITY_INSERT dbo." + table + " ON");
            try {
                DatabaseOperation.INSERT.execute(dbUnit, xmlDataSet("/datasets/" + table + ".xml"));
            } finally {
                exec("SET IDENTITY_INSERT dbo." + table + " OFF");
            }
        }
        try (Statement st = jdbc.createStatement()) {
            st.execute("DBCC CHECKIDENT ('dbo.Booking', RESEED, 101)");
        }
    }

    private IDataSet xmlDataSet(String resource) throws Exception {
        try (InputStream input = getClass().getResourceAsStream(resource)) {
            assertNotNull(input, "Missing DBUnit dataset resource: " + resource);
            return new FlatXmlDataSetBuilder().build(input);
        }
    }
}
