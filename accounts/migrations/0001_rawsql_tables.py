from django.db import migrations

class Migration(migrations.Migration):

    initial = True

    dependencies = []
    
    operations = [
        migrations.RunSQL("""
            CREATE TABLE departments (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );
                          
            CREATE TABLE majors (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                department_id INTEGER NOT NULL,
                FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE
            );

            CREATE TABLE subjects (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT
            );
                          
            CREATE TABLE major_subjects (
                major_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                PRIMARY KEY (major_id, subject_id),
                FOREIGN KEY (major_id) REFERENCES majors(id) ON DELETE CASCADE,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
            );

            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                
                first_name TEXT,
                last_name TEXT,
                avatar_path TEXT,
                
                coins INTEGER DEFAULT 0,
                last_checkin DATE
            );
                          
            CREATE TABLE students (
                student_code TEXT UNIQUE,
                enrollment_year INTEGER,
                          
                id INTEGER PRIMARY KEY,
                major_id INTEGER,
                FOREIGN KEY (id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (major_id) REFERENCES majors(id)
            );
                          
            CREATE TABLE teachers (
                id INTEGER PRIMARY KEY,
                teacher_code TEXT UNIQUE,
                title TEXT,
                degree TEXT,
                          
                department_id INTEGER,
                FOREIGN KEY (id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (department_id) REFERENCES departments(id)
            );


            INSERT INTO departments (name)
            VALUES
                ('Công nghệ Thông tin'),
                ('An toàn Thông tin'),
                ('Đa phương tiện'),
                ('Điện - Điện tử'),
                ('Điện tử Viễn thông'),
                ('Tài chính - Kế toán'),
                ('Trí tuệ Nhân tạo');
                          
            INSERT INTO majors (name, department_id)
            VALUES
                ('Công nghệ Thông tin', 1),
                ('An toàn thông tin', 2),
                ('Công nghệ đa phương tiện', 3),
                ('Công nghệ kỹ thuật điện, điện tử', 4),
                ('Khoa học máy tính', 1),
                ('Kỹ thuật Điện tử Viễn thông', 5),
                ('Công nghệ tài chính (Fintech)', 6),
                ('Mạng máy tính và Truyền thông dữ liệu', 1),
                ('Trí tuệ nhân tạo', 7);
                          
            INSERT INTO subjects (name, description) 
            VALUES
                ('Lập trình C', 'Học các khái niệm lập trình cơ bản nhất thông qua ngôn ngữ C (biến, vòng lặp, hàm, con trỏ).'),
                ('Cấu trúc dữ liệu và giải thuật', 'Nghiên cứu cách tổ chức dữ liệu (mảng, danh sách, cây, đồ thị) và các phương pháp giải quyết bài toán hiệu quả.'),
                ('Cơ sở dữ liệu', 'Tìm hiểu về hệ quản trị cơ sở dữ liệu quan hệ (RDBMS), ngôn ngữ truy vấn SQL, và thiết kế cơ sở dữ liệu.'),
                ('Mạng máy tính', 'Khám phá các nguyên tắc và giao thức mạng, bao gồm mô hình OSI, TCP/IP, định tuyến và bảo mật mạng.'),
                ('Hệ điều hành', 'Nghiên cứu các khái niệm về hệ điều hành như quản lý tiến trình, bộ nhớ, hệ thống tập tin.'),
                ('Kiến trúc máy tính', 'Nghiên cứu cấu trúc và hoạt động của phần cứng máy tính (CPU, bộ nhớ, các thành phần khác).'),
                ('Nhập môn Trí tuệ nhân tạo', 'Giới thiệu về các khái niệm và kỹ thuật trong trí tuệ nhân tạo, bao gồm học máy, xử lý ngôn ngữ tự nhiên.'),
                ('Cơ sở An toàn thông tin', 'Tìm hiểu về các nguyên tắc bảo mật, mã hóa, xác thực và các biện pháp bảo vệ hệ thống thông tin.'),
                ('Lập trình hướng đối tượng', 'Học các nguyên lý lập trình hiện đại (Java/C#/C++) như lớp, đối tượng, kế thừa, đa hình.');

            -- no one in their right mind would manually write this by hand right? RIGHT?

            INSERT INTO major_subjects (major_id, subject_id)
            VALUES
                -- Ngành Công nghệ Thông tin
                (1, 1), (1, 2), (1, 3), (1, 4),
                (1, 5), (1, 6), (1, 7), (1, 8), (1, 9),

                -- Ngành An toàn Thông tin
                (2, 1), (2, 2), (2, 3), (2, 4),
                (2, 5),         (2, 7), (2, 8), (2, 9),
                          
                -- Ngành Công nghệ đa phương tiện
                (3, 1),         (3, 3),
                          
                -- Ngành Công nghệ kỹ thuật điện, điện tử
                (4, 1), (4, 2),
                          
                -- Ngành Khoa học máy tính
                (5, 1), (5, 2), (5, 3), (5, 4),
                        (5, 6),                 (5, 9),
                          
                -- Ngành Kỹ thuật Điện tử Viễn thông
                (6, 1), (6, 2),
                
                -- Ngành Công nghệ tài chính (Fintech)
                (7, 1),
                          
                -- Ngành Mạng máy tính và Truyền thông dữ liệu
                                        (8, 4),
                (8, 5),                 (8, 8), (8, 9),
                          
                -- Ngành Trí tuệ nhân tạo
                        (9, 6),                 (9, 9);
        """),
            
    ]