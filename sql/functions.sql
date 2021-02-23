SET GLOBAL log_bin_trust_function_creators = 1;

DELIMITER //

DROP FUNCTION IF EXISTS `mmeds_data1`.`set_connection_auth` //
CREATE FUNCTION `mmeds_data1`.`set_connection_auth` (v_user VARCHAR(100), v_security_token VARCHAR(100))
RETURNS BOOLEAN
NOT DETERMINISTIC
MODIFIES SQL DATA
SQL SECURITY DEFINER
BEGIN
    SELECT COUNT(*) INTO @v_token_count
    FROM `mmeds_data1`.`security_token`
    WHERE username = SESSION_USER() AND security_token = v_security_token;

    IF @v_token_count < 1 THEN
        RETURN false;
    END IF;
    INSERT INTO `mmeds_datat1`.`session` (connection_id, username) VALUES (CONNECTION_ID(), v_user);
    RETURN true;
END //

DROP FUNCTION IF EXISTS `mmeds_data1`.`unset_connection_auth` //
CREATE FUNCTION `mmeds_data1`.`unset_connection_auth` (v_security_token VARCHAR(100))
RETURNS BOOLEAN
NOT DETERMINISTIC
MODIFIES SQL DATA
SQL SECURITY DEFINER
BEGIN
    DELETE FROM `mmeds_data1`.`session` WHERE connection_id = CONNECTION_ID();
    RETURN true;
END //

DROP FUNCTION IF EXISTS `mmeds_data1`.`owner_check` //
CREATE FUNCTION `mmeds_data1`.`owner_check` (v_owner_user_id int)
RETURNS BOOLEAN
NOT DETERMINISTIC
READS SQL DATA
SQL SECURITY INVOKER
BEGIN
    SELECT u.user_id INTO @v_current_user_id
    FROM session s
    JOIN user u
    ON u.username = s.username
    WHERE s.connection_id = CONNECTION_ID();
    IF @v_current_user_id = v_owner_user_id OR 1 = v_owner_user_id THEN
        RETURN true;
    ELSE
        RETURN false;
    END IF;
END //
DELIMITER ;

-- -----------------------------------------------------
-- Table `mmeds_data1`.`user`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `mmeds_data1`.`user` ;
CREATE TABLE IF NOT EXISTS `mmeds_data1`.`user` (
    `user_id` int NOT NULL PRIMARY KEY,
    `username` varchar(100),
    `password` varchar(64),
    `salt` varchar(10),
    `email` varchar(100),
    `privilege` int
);

-- -----------------------------------------------------
-- Table `mmeds_data1`.`security_token`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `mmeds_data1`.`security_token` ;
CREATE TABLE IF NOT EXISTS `mmeds_data1`.`security_token` (
    security_token_id int NOT NULL AUTO_INCREMENT PRIMARY KEY,
    username varchar(100),
    security_token varchar(100)
);

-- -----------------------------------------------------
-- Table `mmeds_data1`.`session`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `mmeds_data1`.`session` ;
CREATE TABLE IF NOT EXISTS `mmeds_data1`.`session` (
    connection_id int NOT NULL PRIMARY KEY,
    username varchar(100)
);
