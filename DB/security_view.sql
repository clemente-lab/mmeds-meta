CREATE
SQL SECURITY DEFINER
VIEW protected_Aliquot AS
SELECT cc.* FROM `mmeds`.`Aliquot` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Aliquot` TO 'mmeds_user'@'%';

CREATE
SQL SECURITY DEFINER
VIEW protected_BodySite AS
SELECT cc.* FROM `mmeds`.`BodySite` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_BodySite` TO 'mmeds_user'@'%';

CREATE
SQL SECURITY DEFINER
VIEW protected_Ethnicity AS
SELECT cc.* FROM `mmeds`.`Ethnicity` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Ethnicity` TO 'mmeds_user'@'%';

CREATE
SQL SECURITY DEFINER
VIEW protected_Genotypes AS
SELECT cc.* FROM `mmeds`.`Genotypes` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Genotypes` TO 'mmeds_user'@'%';

CREATE
SQL SECURITY DEFINER
VIEW protected_Illness AS
SELECT cc.* FROM `mmeds`.`Illness` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Illness` TO 'mmeds_user'@'%';

CREATE
SQL SECURITY DEFINER
VIEW protected_Illnesses AS
SELECT cc.* FROM `mmeds`.`Illnesses` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Illnesses` TO 'mmeds_user'@'%';

CREATE
SQL SECURITY DEFINER
VIEW protected_Intervention AS
SELECT cc.* FROM `mmeds`.`Intervention` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Intervention` TO 'mmeds_user'@'%';

CREATE
SQL SECURITY DEFINER
VIEW protected_Interventions AS
SELECT cc.* FROM `mmeds`.`Interventions` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Interventions` TO 'mmeds_user'@'%';

CREATE
SQL SECURITY DEFINER
VIEW protected_Lab AS
SELECT cc.* FROM `mmeds`.`Lab` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Lab` TO 'mmeds_user'@'%';

CREATE
SQL SECURITY DEFINER
VIEW protected_Location AS
SELECT cc.* FROM `mmeds`.`Location` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Location` TO 'mmeds_user'@'%';

CREATE
SQL SECURITY DEFINER
VIEW protected_RawData AS
SELECT cc.* FROM `mmeds`.`RawData` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_RawData` TO 'mmeds_user'@'%';

CREATE
SQL SECURITY DEFINER
VIEW protected_RawDataProtocol AS
SELECT cc.* FROM `mmeds`.`RawDataProtocol` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_RawDataProtocol` TO 'mmeds_user'@'%';

CREATE
SQL SECURITY DEFINER
VIEW protected_RawDataProtocols AS
SELECT cc.* FROM `mmeds`.`RawDataProtocols` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_RawDataProtocols` TO 'mmeds_user'@'%';

CREATE
SQL SECURITY DEFINER
VIEW protected_Results AS
SELECT cc.* FROM `mmeds`.`Results` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Results` TO 'mmeds_user'@'%';

CREATE
SQL SECURITY DEFINER
VIEW protected_ResultsProtocol AS
SELECT cc.* FROM `mmeds`.`ResultsProtocol` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_ResultsProtocol` TO 'mmeds_user'@'%';

CREATE
SQL SECURITY DEFINER
VIEW protected_ResultsProtocols AS
SELECT cc.* FROM `mmeds`.`ResultsProtocols` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_ResultsProtocols` TO 'mmeds_user'@'%';

CREATE
SQL SECURITY DEFINER
VIEW protected_Sample AS
SELECT cc.* FROM `mmeds`.`Sample` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Sample` TO 'mmeds_user'@'%';

CREATE
SQL SECURITY DEFINER
VIEW protected_SampleProtocol AS
SELECT cc.* FROM `mmeds`.`SampleProtocol` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_SampleProtocol` TO 'mmeds_user'@'%';

CREATE
SQL SECURITY DEFINER
VIEW protected_SampleProtocols AS
SELECT cc.* FROM `mmeds`.`SampleProtocols` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_SampleProtocols` TO 'mmeds_user'@'%';

CREATE
SQL SECURITY DEFINER
VIEW protected_Specimen AS
SELECT cc.* FROM `mmeds`.`Specimen` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Specimen` TO 'mmeds_user'@'%';

CREATE
SQL SECURITY DEFINER
VIEW protected_Study AS
SELECT cc.* FROM `mmeds`.`Study` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Study` TO 'mmeds_user'@'%';

CREATE
SQL SECURITY DEFINER
VIEW protected_Subjects AS
SELECT cc.* FROM `mmeds`.`Subjects` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Subjects` TO 'mmeds_user'@'%';

CREATE
SQL SECURITY DEFINER
VIEW protected_Type AS
SELECT cc.* FROM `mmeds`.`Type` cc WHERE owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds`.`protected_Type` TO 'mmeds_user'@'%';

