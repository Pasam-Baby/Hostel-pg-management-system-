import sqlite3
con = sqlite3.connect('hostel.db')
cur = con.cursor()

# Check complaints
print('Complaints status:')
complaints = cur.execute("SELECT status, COUNT(*) FROM complaints GROUP BY status").fetchall()
for status, count in complaints:
    print(f'  {status}: {count}')

# Check occupied rooms
print('\nOccupied rooms:')
occupied = cur.execute("SELECT COUNT(DISTINCT room_id) FROM students WHERE room_id IS NOT NULL").fetchone()[0]
print(f'  Occupied: {occupied}')

available = cur.execute("SELECT COUNT(*) FROM rooms WHERE occupied < capacity").fetchone()[0]
print(f'  Available: {available}')

# Check monthly revenue
print('\nMonthly revenue:')
monthly = cur.execute("SELECT strftime('%Y-%m', payment_date) as month, SUM(amount) as total FROM payments GROUP BY month ORDER BY month DESC LIMIT 6").fetchall()
for month, total in monthly:
    print(f'  {month}: ₹{total}')

con.close()