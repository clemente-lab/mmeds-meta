DROP VIEW IF EXISTS `mmeds_data1`.`protected_Aliquot`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Aliquot` AS
SELECT cc.* FROM `mmeds_data1`.`Aliquot` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Aliquot` TO 'mmedsusers'@"localhost";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Experiment`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Experiment` AS
SELECT cc.* FROM `mmeds_data1`.`Experiment` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Experiment` TO 'mmedsusers'@"localhost";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Heights`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Heights` AS
SELECT cc.* FROM `mmeds_data1`.`Heights` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Heights` TO 'mmedsusers'@"localhost";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Illness`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Illness` AS
SELECT cc.* FROM `mmeds_data1`.`Illness` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Illness` TO 'mmedsusers'@"localhost";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Intervention`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Intervention` AS
SELECT cc.* FROM `mmeds_data1`.`Intervention` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Intervention` TO 'mmedsusers'@"localhost";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Lab`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Lab` AS
SELECT cc.* FROM `mmeds_data1`.`Lab` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Lab` TO 'mmedsusers'@"localhost";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_RawData`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_RawData` AS
SELECT cc.* FROM `mmeds_data1`.`RawData` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_RawData` TO 'mmedsusers'@"localhost";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_RawDataProtocol`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_RawDataProtocol` AS
SELECT cc.* FROM `mmeds_data1`.`RawDataProtocol` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_RawDataProtocol` TO 'mmedsusers'@"localhost";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Results`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Results` AS
SELECT cc.* FROM `mmeds_data1`.`Results` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Results` TO 'mmedsusers'@"localhost";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_ResultsProtocol`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_ResultsProtocol` AS
SELECT cc.* FROM `mmeds_data1`.`ResultsProtocol` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_ResultsProtocol` TO 'mmedsusers'@"localhost";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Sample`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Sample` AS
SELECT cc.* FROM `mmeds_data1`.`Sample` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Sample` TO 'mmedsusers'@"localhost";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_SampleProtocol`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_SampleProtocol` AS
SELECT cc.* FROM `mmeds_data1`.`SampleProtocol` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_SampleProtocol` TO 'mmedsusers'@"localhost";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Specimen`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Specimen` AS
SELECT cc.* FROM `mmeds_data1`.`Specimen` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Specimen` TO 'mmedsusers'@"localhost";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Study`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Study` AS
SELECT cc.* FROM `mmeds_data1`.`Study` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Study` TO 'mmedsusers'@"localhost";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Subjects`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Subjects` AS
SELECT cc.* FROM `mmeds_data1`.`Subjects` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Subjects` TO 'mmedsusers'@"localhost";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Weights`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Weights` AS
SELECT cc.* FROM `mmeds_data1`.`Weights` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Weights` TO 'mmedsusers'@"localhost";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_ChowDates`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_ChowDates` AS
SELECT cc.* FROM `mmeds_data1`.`ChowDates` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_ChowDates` TO 'mmedsusers'@"localhost";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_HousingDates`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_HousingDates` AS
SELECT cc.* FROM `mmeds_data1`.`HousingDates` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_HousingDates` TO 'mmedsusers'@"localhost";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_Husbandry`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_Husbandry` AS
SELECT cc.* FROM `mmeds_data1`.`Husbandry` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_Husbandry` TO 'mmedsusers'@"localhost";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_AnimalSubjects`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_AnimalSubjects` AS
SELECT cc.* FROM `mmeds_data1`.`AnimalSubjects` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_AnimalSubjects` TO 'mmedsusers'@"localhost";

DROP VIEW IF EXISTS `mmeds_data1`.`protected_SubjectType`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`protected_SubjectType` AS
SELECT cc.* FROM `mmeds_data1`.`SubjectType` cc WHERE `mmeds_data1`.owner_check(cc.user_id)
WITH CHECK OPTION;

DROP VIEW IF EXISTS `mmeds_data1`.`SubjectTable`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`SubjectTable` AS
SELECT DISTINCT idSubjects, idSubjectType AS idSubjectTypeHuman, Ethnicity, Genotype, Height, HeightDateCollected, CONCAT(ICDFirstCharacter, ICDCategory, '.', ICDDetails, ICDExtension) AS ICDCode,IllnessInstanceID, IllnessStartDate, IllnessEndDate, IllnessNotes, InterventionStartDate, InterventionEndDate, InterventionNotes, InterventionCode, InterventionName, InterventionType, BirthYear, HostSubjectId, Nationality, Sex AS SexHuman, Weight, WeightDateCollected from Subjects INNER JOIN (Subjects_has_Ethnicity INNER JOIN Ethnicity ON Subjects_has_Ethnicity.Ethnicity_idEthnicity=Ethnicity.idEthnicity) ON Subjects.idSubjects=Subjects_has_Ethnicity.Subjects_idSubjects INNER JOIN (Subjects_has_Genotypes INNER JOIN Genotypes ON Subjects_has_Genotypes.Genotypes_idGenotypes=Genotypes.idGenotypes) ON Subjects.idSubjects=Subjects_has_Genotypes.Subjects_idSubjects INNER JOIN Heights ON Subjects.idSubjects=Heights.Subjects_idSubjects INNER JOIN (Illness INNER JOIN (IllnessDetails INNER JOIN (IllnessCategory INNER JOIN IllnessBroadCategory ON IllnessBroadCategory.idIllnessBroadCategory=IllnessCategory.IllnessBroadCategory_idIllnessBroadCategory) ON IllnessCategory.idIllnessCategory=IllnessDetails.IllnessCategory_idIllnessCategory) ON IllnessDetails.idIllnessDetails=Illness.IllnessDetails_idIllnessDetails) ON Subjects.idSubjects=Illness.Subjects_idSubjects INNER JOIN (Intervention INNER JOIN Interventions ON Interventions.idInterventions=Intervention.Interventions_idInterventions) ON Subjects.idSubjects=Intervention.Subjects_idSubjects INNER JOIN Weights ON Subjects.idSubjects=Weights.Subjects_idSubjects INNER JOIN SubjectType ON Subjects.idSubjects=SubjectType.Subjects_idSubjects
WITH CHECK OPTION;

DROP VIEW IF EXISTS `mmeds_data1`.`AnimalSubjectTable`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`AnimalSubjectTable` AS
SELECT DISTINCT idAnimalSubjects, idSubjectType AS idSubjectTypeAnimal, BirthDate, AnimalWeight, Sex AS SexAnimal, AnimalSubjectID, SubjectType, FacilityName, FacilityLocation, VendorName, VendorLocation, VendorStrainInfo, StrainName, StrainProducer, StrainID, SpeciesName, BreedingProgram, LightDarkCycle, Temperature, EnvironmentalEnrichment, TypeOfFacility, TypeOfBedding, TypeOfHousing, NumberOfCageCompanions, TankShape, TankMaterial, TankID, HousingStartDate, HousingEndDate, ChowStartDate, ChowEndDate, Company, ProductName, ProductCode FROM AnimalSubjects INNER JOIN SubjectType ON AnimalSubjects.idAnimalSubjects=SubjectType.AnimalSubjects_idAnimalSubjects INNER JOIN Facility ON AnimalSubjects.Facility_idFacility=Facility.idFacility INNER JOIN Vendor ON AnimalSubjects.Vendor_idVendor=Vendor.idVendor INNER JOIN (Strain INNER JOIN Species ON Strain.Species_idSpecies=Species.idSpecies) ON AnimalSubjects.Strain_idStrain=Strain.idStrain INNER JOIN Husbandry ON AnimalSubjects.Husbandry_idHusbandry=Husbandry.idHusbandry INNER JOIN (HousingDates INNER JOIN Housing ON HousingDates.Housing_idHousing=Housing.idHousing) ON AnimalSubjects.idAnimalSubjects=HousingDates.AnimalSubjects_idAnimalSubjects INNER JOIN (ChowDates INNER JOIN Chow ON ChowDates.Chow_idChow=Chow.idChow) ON AnimalSubjects.ChowDates_idChowDates=ChowDates.idChowDates
WITH CHECK OPTION;

DROP VIEW IF EXISTS `mmeds_data1`.`SpecimenTable`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`SpecimenTable` AS
SELECT DISTINCT idSpecimen, idSubjectType, AliquotID, AliquotWeight, AliquotWeightUnit, SpecimenBodySite, UberonCodeBodySite, Biome, CollectionSiteName, CollectionSiteTechnician, Depth, Elevation, Environment, Feature, Latitude, Longitude, Material, ExperimentName, ContactEmail, ContactName, PrimaryInvestigator, BarcodeSequence, LinkerPrimerSequence, RawDataID, RawDataNotes, RawDataDatePerformed, RawDataProcessor, RawDataProtocolID, FinishingStrategyCoverage, FinishingStrategyStatus, NumberOfContigs, SequencingMethod, TargetGene, ResultID, ResultsLocation, ResultsDatePerformed, ResultsProcessor, ResultsProtocolID, ResultsMethod, ResultsTool, ResultsToolVersion, SampleID, SampleWeight, SampleWeightUnit, SampleDatePerformed, SampleProcessor, SampleProtocolID, SampleProtocolNotes, SampleConditions, SampleTool, SampleToolVersion, SpecimenCollectionDate, SpecimenCollectionMethod, SpecimenCollectionTime, SpecimenID, SpecimenNotes, SpecimenWeight, SpecimenWeightUnit, StorageInstitution, StorageFreezer, RelevantLinks, StudyName, StudyType, SpecimenType, UberonCodeType FROM Specimen INNER JOIN Aliquot ON Specimen.idSpecimen=Aliquot.Specimen_idSpecimen INNER JOIN BodySite ON Specimen.BodySite_idBodySite=BodySite.idBodySite INNER JOIN CollectionSite ON Specimen.CollectionSite_idCollectionSite=CollectionSite.idCollectionSite INNER JOIN (Experiment INNER JOIN (Study INNER JOIN Lab ON Study.Lab_idLab=Lab.idLab) ON Experiment.Study_idStudy=Study.idStudy) ON Specimen.Experiment_idExperiment=Experiment.idExperiment INNER JOIN (StorageLocation INNER JOIN (Sample INNER JOIN (RawData INNER JOIN (RawDataProtocol INNER JOIN RawDataProtocols ON RawDataProtocol.RawDataProtocols_idRawDataProtocols=RawDataProtocols.idRawDataProtocols) ON RawData.RawDataProtocol_idRawDataProtocol=RawDataProtocol.idRawDataProtocol INNER JOIN (Results INNER JOIN (ResultsProtocol INNER JOIN ResultsProtocols ON ResultsProtocol.ResultsProtocols_idResultsProtocols=ResultsProtocols.idResultsProtocols) ON Results.ResultsProtocol_idResultsProtocol=ResultsProtocol.idResultsProtocol) ON RawData.Sample_idSample=Results.RawData_Sample_idSample) ON Sample.idSample=RawData.Sample_idSample INNER JOIN (SampleProtocol INNER JOIN SampleProtocols ON SampleProtocol.SampleProtocols_idSampleProtocols=SampleProtocols.idSampleProtocols) ON Sample.SampleProtocol_idSampleProtocol=SampleProtocol.idSampleProtocol) ON StorageLocation.idStorageLocation=Sample.StorageLocation_idStorageLocation) ON Specimen.StorageLocation_idStorageLocation=StorageLocation.idStorageLocation INNER JOIN Type ON Specimen.Type_idType=Type.idType INNER JOIN SubjectType ON Specimen.SubjectType_idSubjectType=SubjectType.idSubjectType
WITH CHECK OPTION;

DROP VIEW IF EXISTS `mmeds_data1`.`MetaAnalysisView`;
CREATE
SQL SECURITY DEFINER
VIEW `mmeds_data1`.`MetaAnalysisView` AS
SELECT DISTINCT * FROM SpecimenTable INNER JOIN SubjectTable ON SpecimenTable.idSubjectType=SubjectTable.idSubjectTypeHuman INNER JOIN AnimalSubjectTable ON SpecimenTable.idSubjectType=AnimalSubjectTable.idSubjectTypeAnimal
WITH CHECK OPTION;

GRANT SELECT ON TABLE `mmeds_data1`.`protected_SubjectType` TO 'mmedsusers'@"localhost";

GRANT SELECT ON TABLE `mmeds_data1`.`Type` TO 'mmedsusers'@"localhost";

GRANT SELECT ON TABLE `mmeds_data1`.`Facility` TO 'mmedsusers'@"localhost";

GRANT SELECT ON TABLE `mmeds_data1`.`CollectionSite` TO 'mmedsusers'@"localhost";

GRANT SELECT ON TABLE `mmeds_data1`.`BodySite` TO 'mmedsusers'@"localhost";

GRANT SELECT ON TABLE `mmeds_data1`.`Vendor` TO 'mmedsusers'@"localhost";

GRANT SELECT ON TABLE `mmeds_data1`.`IllnessCategory` TO 'mmedsusers'@"localhost";

GRANT SELECT ON TABLE `mmeds_data1`.`Species` TO 'mmedsusers'@"localhost";

GRANT SELECT ON TABLE `mmeds_data1`.`Housing` TO 'mmedsusers'@"localhost";

GRANT SELECT ON TABLE `mmeds_data1`.`RawDataProtocols` TO 'mmedsusers'@"localhost";

GRANT SELECT ON TABLE `mmeds_data1`.`Genotypes` TO 'mmedsusers'@"localhost";

GRANT SELECT ON TABLE `mmeds_data1`.`IllnessBroadCategory` TO 'mmedsusers'@"localhost";

GRANT SELECT ON TABLE `mmeds_data1`.`SampleProtocols` TO 'mmedsusers'@"localhost";

GRANT SELECT ON TABLE `mmeds_data1`.`ResultsProtocols` TO 'mmedsusers'@"localhost";

GRANT SELECT ON TABLE `mmeds_data1`.`IllnessDetails` TO 'mmedsusers'@"localhost";

GRANT SELECT ON TABLE `mmeds_data1`.`Ethnicity` TO 'mmedsusers'@"localhost";

GRANT SELECT ON TABLE `mmeds_data1`.`StorageLocation` TO 'mmedsusers'@"localhost";

GRANT SELECT ON TABLE `mmeds_data1`.`Strain` TO 'mmedsusers'@"localhost";

GRANT SELECT ON TABLE `mmeds_data1`.`Interventions` TO 'mmedsusers'@"localhost";

GRANT SELECT ON TABLE `mmeds_data1`.`Chow` TO 'mmedsusers'@"localhost";

