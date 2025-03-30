CREATE TABLE trading_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    date DATE,
	ticker VARCHAR(50),
    companyname VARCHAR(100),
    change_perc FLOAT,
    volume_price FLOAT,
    market_cap FLOAT,
    industry VARCHAR(100)
);
