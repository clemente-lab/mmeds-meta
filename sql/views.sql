DROP VIEW IF EXISTS `mmeds_data1`.`protected_Lab`;
CREATE
SQL SECURITY DEFINER
VIEW protected_Lab AS
SELECT cc.* FROM `mmeds_data1`.`Lab` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Lab` TO 'mmeds_data1_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Study`;
CREATE
SQL SECURITY DEFINER
VIEW protected_Study AS
SELECT cc.* FROM `mmeds_data1`.`Study` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Study` TO 'mmeds_data1_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Experiment`;
CREATE
SQL SECURITY DEFINER
VIEW protected_Experiment AS
SELECT cc.* FROM `mmeds_data1`.`Experiment` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Experiment` TO 'mmeds_data1_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Location`;
CREATE
SQL SECURITY DEFINER
VIEW protected_Location AS
SELECT cc.* FROM `mmeds_data1`.`Location` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Location` TO 'mmeds_data1_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Subjects`;
CREATE
SQL SECURITY DEFINER
VIEW protected_Subjects AS
SELECT cc.* FROM `mmeds_data1`.`Subjects` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Subjects` TO 'mmeds_data1_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Illness`;
CREATE
SQL SECURITY DEFINER
VIEW protected_Illness AS
SELECT cc.* FROM `mmeds_data1`.`Illness` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Illness` TO 'mmeds_data1_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Intervention`;
CREATE
SQL SECURITY DEFINER
VIEW protected_Intervention AS
SELECT cc.* FROM `mmeds_data1`.`Intervention` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Intervention` TO 'mmeds_data1_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Specimen`;
CREATE
SQL SECURITY DEFINER
VIEW protected_Specimen AS
SELECT cc.* FROM `mmeds_data1`.`Specimen` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Specimen` TO 'mmeds_data1_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Aliquot`;
CREATE
SQL SECURITY DEFINER
VIEW protected_Aliquot AS
SELECT cc.* FROM `mmeds_data1`.`Aliquot` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Aliquot` TO 'mmeds_data1_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_SampleProtocol`;
CREATE
SQL SECURITY DEFINER
VIEW protected_SampleProtocol AS
SELECT cc.* FROM `mmeds_data1`.`SampleProtocol` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_SampleProtocol` TO 'mmeds_data1_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Sample`;
CREATE
SQL SECURITY DEFINER
VIEW protected_Sample AS
SELECT cc.* FROM `mmeds_data1`.`Sample` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Sample` TO 'mmeds_data1_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_RawDataProtocol`;
CREATE
SQL SECURITY DEFINER
VIEW protected_RawDataProtocol AS
SELECT cc.* FROM `mmeds_data1`.`RawDataProtocol` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_RawDataProtocol` TO 'mmeds_data1_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_RawData`;
CREATE
SQL SECURITY DEFINER
VIEW protected_RawData AS
SELECT cc.* FROM `mmeds_data1`.`RawData` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_RawData` TO 'mmeds_data1_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_ResultsProtocol`;
CREATE
SQL SECURITY DEFINER
VIEW protected_ResultsProtocol AS
SELECT cc.* FROM `mmeds_data1`.`ResultsProtocol` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_ResultsProtocol` TO 'mmeds_data1_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Results`;
CREATE
SQL SECURITY DEFINER
VIEW protected_Results AS
SELECT cc.* FROM `mmeds_data1`.`Results` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Results` TO 'mmeds_data1_user'@'%';

GRANT SELECT ON TABLE `mmeds_data1`.`Genotypes` TO 'mmeds_data1_user'@'%';

GRANT SELECT ON TABLE `mmeds_data1`.`Type` TO 'mmeds_data1_user'@'%';

GRANT SELECT ON TABLE `mmeds_data1`.`RawDataProtocols` TO 'mmeds_data1_user'@'%';

GRANT SELECT ON TABLE `mmeds_data1`.`Ethnicity` TO 'mmeds_data1_user'@'%';

GRANT SELECT ON TABLE `mmeds_data1`.`BodySite` TO 'mmeds_data1_user'@'%';

GRANT SELECT ON TABLE `mmeds_data1`.`Illnesses` TO 'mmeds_data1_user'@'%';

GRANT SELECT ON TABLE `mmeds_data1`.`Interventions` TO 'mmeds_data1_user'@'%';

GRANT SELECT ON TABLE `mmeds_data1`.`ResultsProtocols` TO 'mmeds_data1_user'@'%';

GRANT SELECT ON TABLE `mmeds_data1`.`SampleProtocols` TO 'mmeds_data1_user'@'%';

