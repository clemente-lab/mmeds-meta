DROP VIEW IF EXISTS `mmeds_data1`.`protected_Aliquot`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Aliquot` AS
SELECT cc.* FROM `mmeds_data1`.`Aliquot` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Aliquot` TO 'mmedsusers'@"%";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Experiment`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Experiment` AS
SELECT cc.* FROM `mmeds_data1`.`Experiment` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Experiment` TO 'mmedsusers'@"%";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Heights`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Heights` AS
SELECT cc.* FROM `mmeds_data1`.`Heights` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Heights` TO 'mmedsusers'@"%";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Illness`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Illness` AS
SELECT cc.* FROM `mmeds_data1`.`Illness` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Illness` TO 'mmedsusers'@"%";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Intervention`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Intervention` AS
SELECT cc.* FROM `mmeds_data1`.`Intervention` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Intervention` TO 'mmedsusers'@"%";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Lab`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Lab` AS
SELECT cc.* FROM `mmeds_data1`.`Lab` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Lab` TO 'mmedsusers'@"%";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_RawData`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_RawData` AS
SELECT cc.* FROM `mmeds_data1`.`RawData` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_RawData` TO 'mmedsusers'@"%";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_RawDataProtocol`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_RawDataProtocol` AS
SELECT cc.* FROM `mmeds_data1`.`RawDataProtocol` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_RawDataProtocol` TO 'mmedsusers'@"%";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Results`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Results` AS
SELECT cc.* FROM `mmeds_data1`.`Results` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Results` TO 'mmedsusers'@"%";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_ResultsProtocol`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_ResultsProtocol` AS
SELECT cc.* FROM `mmeds_data1`.`ResultsProtocol` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_ResultsProtocol` TO 'mmedsusers'@"%";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Sample`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Sample` AS
SELECT cc.* FROM `mmeds_data1`.`Sample` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Sample` TO 'mmedsusers'@"%";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_SampleProtocol`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_SampleProtocol` AS
SELECT cc.* FROM `mmeds_data1`.`SampleProtocol` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_SampleProtocol` TO 'mmedsusers'@"%";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Specimen`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Specimen` AS
SELECT cc.* FROM `mmeds_data1`.`Specimen` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Specimen` TO 'mmedsusers'@"%";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Study`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Study` AS
SELECT cc.* FROM `mmeds_data1`.`Study` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Study` TO 'mmedsusers'@"%";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Subjects`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Subjects` AS
SELECT cc.* FROM `mmeds_data1`.`Subjects` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Subjects` TO 'mmedsusers'@"%";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Weights`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Weights` AS
SELECT cc.* FROM `mmeds_data1`.`Weights` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Weights` TO 'mmedsusers'@"%";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_ChowDates`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_ChowDates` AS
SELECT cc.* FROM `mmeds_data1`.`ChowDates` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_ChowDates` TO 'mmedsusers'@"%";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_HousingDates`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_HousingDates` AS
SELECT cc.* FROM `mmeds_data1`.`HousingDates` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_HousingDates` TO 'mmedsusers'@"%";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Husbandry`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Husbandry` AS
SELECT cc.* FROM `mmeds_data1`.`Husbandry` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Husbandry` TO 'mmedsusers'@"%";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_AnimalSubjects`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_AnimalSubjects` AS
SELECT cc.* FROM `mmeds_data1`.`AnimalSubjects` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_AnimalSubjects` TO 'mmedsusers'@"%";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_SubjectType`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_SubjectType` AS
SELECT cc.* FROM `mmeds_data1`.`SubjectType` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_SubjectType` TO 'mmedsusers'@"%";

GRANT SELECT ON TABLE `mmeds_data1`.`BodySite` TO 'mmedsusers'@"%";

GRANT SELECT ON TABLE `mmeds_data1`.`Facility` TO 'mmedsusers'@"%";

GRANT SELECT ON TABLE `mmeds_data1`.`Chow` TO 'mmedsusers'@"%";

GRANT SELECT ON TABLE `mmeds_data1`.`Strain` TO 'mmedsusers'@"%";

GRANT SELECT ON TABLE `mmeds_data1`.`SampleProtocols` TO 'mmedsusers'@"%";

GRANT SELECT ON TABLE `mmeds_data1`.`Housing` TO 'mmedsusers'@"%";

GRANT SELECT ON TABLE `mmeds_data1`.`IllnessCategory` TO 'mmedsusers'@"%";

GRANT SELECT ON TABLE `mmeds_data1`.`Ethnicity` TO 'mmedsusers'@"%";

GRANT SELECT ON TABLE `mmeds_data1`.`Genotypes` TO 'mmedsusers'@"%";

GRANT SELECT ON TABLE `mmeds_data1`.`Type` TO 'mmedsusers'@"%";

GRANT SELECT ON TABLE `mmeds_data1`.`CollectionSite` TO 'mmedsusers'@"%";

GRANT SELECT ON TABLE `mmeds_data1`.`IllnessBroadCategory` TO 'mmedsusers'@"%";

GRANT SELECT ON TABLE `mmeds_data1`.`RawDataProtocols` TO 'mmedsusers'@"%";

GRANT SELECT ON TABLE `mmeds_data1`.`ResultsProtocols` TO 'mmedsusers'@"%";

GRANT SELECT ON TABLE `mmeds_data1`.`Vendor` TO 'mmedsusers'@"%";

GRANT SELECT ON TABLE `mmeds_data1`.`IllnessDetails` TO 'mmedsusers'@"%";

GRANT SELECT ON TABLE `mmeds_data1`.`Species` TO 'mmedsusers'@"%";

GRANT SELECT ON TABLE `mmeds_data1`.`Interventions` TO 'mmedsusers'@"%";

