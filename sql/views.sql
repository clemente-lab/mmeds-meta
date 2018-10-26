DROP VIEW IF EXISTS `mmeds_data1`.`protected_Lab`;
CREATE
SQL SECURITY DEFINER
VIEW protected_mmeds_data1 AS
SELECT cc.* FROM `Lab`.`Lab` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Lab` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Study`;
CREATE
SQL SECURITY DEFINER
VIEW protected_mmeds_data1 AS
SELECT cc.* FROM `Study`.`Study` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Study` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_CollectionSite`;
CREATE
SQL SECURITY DEFINER
VIEW protected_mmeds_data1 AS
SELECT cc.* FROM `CollectionSite`.`CollectionSite` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_CollectionSite` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Experiment`;
CREATE
SQL SECURITY DEFINER
VIEW protected_mmeds_data1 AS
SELECT cc.* FROM `Experiment`.`Experiment` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Experiment` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Subjects`;
CREATE
SQL SECURITY DEFINER
VIEW protected_mmeds_data1 AS
SELECT cc.* FROM `Subjects`.`Subjects` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Subjects` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Illness`;
CREATE
SQL SECURITY DEFINER
VIEW protected_mmeds_data1 AS
SELECT cc.* FROM `Illness`.`Illness` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Illness` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Intervention`;
CREATE
SQL SECURITY DEFINER
VIEW protected_mmeds_data1 AS
SELECT cc.* FROM `Intervention`.`Intervention` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Intervention` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Specimen`;
CREATE
SQL SECURITY DEFINER
VIEW protected_mmeds_data1 AS
SELECT cc.* FROM `Specimen`.`Specimen` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Specimen` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Aliquot`;
CREATE
SQL SECURITY DEFINER
VIEW protected_mmeds_data1 AS
SELECT cc.* FROM `Aliquot`.`Aliquot` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Aliquot` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_SampleProtocol`;
CREATE
SQL SECURITY DEFINER
VIEW protected_mmeds_data1 AS
SELECT cc.* FROM `SampleProtocol`.`SampleProtocol` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_SampleProtocol` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Sample`;
CREATE
SQL SECURITY DEFINER
VIEW protected_mmeds_data1 AS
SELECT cc.* FROM `Sample`.`Sample` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Sample` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_RawDataProtocol`;
CREATE
SQL SECURITY DEFINER
VIEW protected_mmeds_data1 AS
SELECT cc.* FROM `RawDataProtocol`.`RawDataProtocol` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_RawDataProtocol` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_RawData`;
CREATE
SQL SECURITY DEFINER
VIEW protected_mmeds_data1 AS
SELECT cc.* FROM `RawData`.`RawData` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_RawData` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_ResultsProtocol`;
CREATE
SQL SECURITY DEFINER
VIEW protected_mmeds_data1 AS
SELECT cc.* FROM `ResultsProtocol`.`ResultsProtocol` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_ResultsProtocol` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Results`;
CREATE
SQL SECURITY DEFINER
VIEW protected_mmeds_data1 AS
SELECT cc.* FROM `Results`.`Results` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Results` TO 'mmeds_user'@'%';

GRANT SELECT ON TABLE `mmeds_data1`.`RawDataProtocols` TO 'mmeds_user'@'%';

GRANT SELECT ON TABLE `mmeds_data1`.`SampleProtocols` TO 'mmeds_user'@'%';

GRANT SELECT ON TABLE `mmeds_data1`.`Genotypes` TO 'mmeds_user'@'%';

GRANT SELECT ON TABLE `mmeds_data1`.`Interventions` TO 'mmeds_user'@'%';

GRANT SELECT ON TABLE `mmeds_data1`.`Ethnicity` TO 'mmeds_user'@'%';

GRANT SELECT ON TABLE `mmeds_data1`.`BodySite` TO 'mmeds_user'@'%';

GRANT SELECT ON TABLE `mmeds_data1`.`Illnesses` TO 'mmeds_user'@'%';

GRANT SELECT ON TABLE `mmeds_data1`.`ResultsProtocols` TO 'mmeds_user'@'%';

GRANT SELECT ON TABLE `mmeds_data1`.`Type` TO 'mmeds_user'@'%';

