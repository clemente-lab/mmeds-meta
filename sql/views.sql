DROP VIEW IF EXISTS `mmeds`.`protected_Lab`;
CREATE
SQL SECURITY DEFINER
VIEW protected_Lab AS
SELECT cc.* FROM `mmeds`.`Lab` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Lab` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds`.`protected_Study`;
CREATE
SQL SECURITY DEFINER
VIEW protected_Study AS
SELECT cc.* FROM `mmeds`.`Study` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Study` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds`.`protected_Experiment`;
CREATE
SQL SECURITY DEFINER
VIEW protected_Experiment AS
SELECT cc.* FROM `mmeds`.`Experiment` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Experiment` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds`.`protected_Location`;
CREATE
SQL SECURITY DEFINER
VIEW protected_Location AS
SELECT cc.* FROM `mmeds`.`Location` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Location` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds`.`protected_Subjects`;
CREATE
SQL SECURITY DEFINER
VIEW protected_Subjects AS
SELECT cc.* FROM `mmeds`.`Subjects` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Subjects` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds`.`protected_Illness`;
CREATE
SQL SECURITY DEFINER
VIEW protected_Illness AS
SELECT cc.* FROM `mmeds`.`Illness` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Illness` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds`.`protected_Intervention`;
CREATE
SQL SECURITY DEFINER
VIEW protected_Intervention AS
SELECT cc.* FROM `mmeds`.`Intervention` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Intervention` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds`.`protected_Specimen`;
CREATE
SQL SECURITY DEFINER
VIEW protected_Specimen AS
SELECT cc.* FROM `mmeds`.`Specimen` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Specimen` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds`.`protected_Aliquot`;
CREATE
SQL SECURITY DEFINER
VIEW protected_Aliquot AS
SELECT cc.* FROM `mmeds`.`Aliquot` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Aliquot` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds`.`protected_SampleProtocol`;
CREATE
SQL SECURITY DEFINER
VIEW protected_SampleProtocol AS
SELECT cc.* FROM `mmeds`.`SampleProtocol` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_SampleProtocol` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds`.`protected_Sample`;
CREATE
SQL SECURITY DEFINER
VIEW protected_Sample AS
SELECT cc.* FROM `mmeds`.`Sample` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Sample` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds`.`protected_RawDataProtocol`;
CREATE
SQL SECURITY DEFINER
VIEW protected_RawDataProtocol AS
SELECT cc.* FROM `mmeds`.`RawDataProtocol` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_RawDataProtocol` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds`.`protected_RawData`;
CREATE
SQL SECURITY DEFINER
VIEW protected_RawData AS
SELECT cc.* FROM `mmeds`.`RawData` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_RawData` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds`.`protected_ResultsProtocol`;
CREATE
SQL SECURITY DEFINER
VIEW protected_ResultsProtocol AS
SELECT cc.* FROM `mmeds`.`ResultsProtocol` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_ResultsProtocol` TO 'mmeds_user'@'%';

DROP VIEW IF EXISTS `mmeds`.`protected_Results`;
CREATE
SQL SECURITY DEFINER
VIEW protected_Results AS
SELECT cc.* FROM `mmeds`.`Results` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Results` TO 'mmeds_user'@'%';

GRANT SELECT ON TABLE `mmeds`.`Genotypes` TO 'mmeds_user'@'%';

GRANT SELECT ON TABLE `mmeds`.`Type` TO 'mmeds_user'@'%';

GRANT SELECT ON TABLE `mmeds`.`RawDataProtocols` TO 'mmeds_user'@'%';

GRANT SELECT ON TABLE `mmeds`.`Ethnicity` TO 'mmeds_user'@'%';

GRANT SELECT ON TABLE `mmeds`.`BodySite` TO 'mmeds_user'@'%';

GRANT SELECT ON TABLE `mmeds`.`Illnesses` TO 'mmeds_user'@'%';

GRANT SELECT ON TABLE `mmeds`.`Interventions` TO 'mmeds_user'@'%';

GRANT SELECT ON TABLE `mmeds`.`ResultsProtocols` TO 'mmeds_user'@'%';

GRANT SELECT ON TABLE `mmeds`.`SampleProtocols` TO 'mmeds_user'@'%';

