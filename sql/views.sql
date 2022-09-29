
-- ------------------ --
-- Server Table Views --
-- ------------------ --

-- Specimen View --
DROP VIEW IF EXISTS `mmeds_data1`.`SpecimenView`;
CREATE VIEW `mmeds_data1`.`SpecimenView` AS SELECT
`idSpecimen`,
`SpecimenID`,
`Specimen`.`user_id`,
`SpecimenCollectionDate`,
`SpecimenNotes`,
`SpecimenCollectionTime`,
`SpecimenWeight`,
`SpecimenWeightUnit`,
`StudyName`
FROM ( `Specimen` INNER JOIN
    ( `Experiment` INNER JOIN
        `Study` ON `Study_idStudy` = `idStudy` )
    ON `Experiment_idExperiment` = `idExperiment` );

-- Sample View --
DROP VIEW IF EXISTS `mmeds_data1`.`SampleView`;
CREATE VIEW `mmeds_data1`.`SampleView` AS SELECT
`idSample`,
`Aliquot_idAliquot`,
`SampleID`,
`SampleDatePerformed`,
`SampleProcessor`,
`SampleProtocolNotes`,
`SampleProtocolID`,
`SampleConditions`,
`SampleTool`,
`SampleToolVersion`
FROM ( `Sample` INNER JOIN
    ( `SampleProtocol` INNER JOIN
        `SampleProtocols` ON `SampleProtocols_idSampleProtocols` = `idSampleProtocols` )
    ON `SampleProtocol_idSampleProtocol` = `idSampleProtocol` );

-- SubjectType View --
DROP VIEW IF EXISTS `mmeds_data1`.`SubjectTypeView`;
CREATE VIEW `mmeds_data1`.`SubjectTypeView` AS SELECT
`StudyName`,
`Subjects_idSubjects`,
`AnimalSubjects_idAnimalSubjects` FROM
( `SubjectType` INNER JOIN
    (`SubjectType_has_Experiment` INNER JOIN
        ( `Experiment` INNER JOIN
            `Study` ON `Study_idStudy` = `idStudy` )
        ON `Experiment_idExperiment` = `idExperiment`)
    ON `idSubjectType` = `SubjectType_idSubjectType`);


-- Human Subject View --
DROP VIEW IF EXISTS `mmeds_data1`.`SubjectView`;
CREATE VIEW `mmeds_data1`.`SubjectView` AS SELECT
`idSubjects`,
`HostSubjectId`,
`Nationality`,
`Sex`,
`BirthYear`,
`StudyName` FROM
( `Subjects` INNER JOIN `SubjectTypeView` ON `idSubjects` = `Subjects_idSubjects`);

-- Human Subject Full View --
DROP VIEW IF EXISTS `mmeds_data1`.`SubjectTable`;
CREATE VIEW `mmeds_data1`.`SubjectTable` AS
SELECT DISTINCT idSubjects, idSubjectType AS idSubjectTypeHuman, Ethnicity, Genotype, Height, HeightDateCollected, CONCAT(ICDFirstCharacter, ICDCategory, '.', ICDDetails, ICDExtension) AS ICDCode,IllnessInstanceID, IllnessStartDate, IllnessEndDate, IllnessNotes, InterventionStartDate, InterventionEndDate, InterventionNotes, InterventionCode, InterventionName, InterventionType, BirthYear, HostSubjectId, Nationality, Sex AS SexHuman, Weight, WeightDateCollected from Subjects INNER JOIN (Subjects_has_Ethnicity INNER JOIN Ethnicity ON Subjects_has_Ethnicity.Ethnicity_idEthnicity=Ethnicity.idEthnicity) ON Subjects.idSubjects=Subjects_has_Ethnicity.Subjects_idSubjects INNER JOIN (Subjects_has_Genotypes INNER JOIN Genotypes ON Subjects_has_Genotypes.Genotypes_idGenotypes=Genotypes.idGenotypes) ON Subjects.idSubjects=Subjects_has_Genotypes.Subjects_idSubjects INNER JOIN Heights ON Subjects.idSubjects=Heights.Subjects_idSubjects INNER JOIN (Illness INNER JOIN (IllnessDetails INNER JOIN (IllnessCategory INNER JOIN IllnessBroadCategory ON IllnessBroadCategory.idIllnessBroadCategory=IllnessCategory.IllnessBroadCategory_idIllnessBroadCategory) ON IllnessCategory.idIllnessCategory=IllnessDetails.IllnessCategory_idIllnessCategory) ON IllnessDetails.idIllnessDetails=Illness.IllnessDetails_idIllnessDetails) ON Subjects.idSubjects=Illness.Subjects_idSubjects INNER JOIN (Intervention INNER JOIN Interventions ON Interventions.idInterventions=Intervention.Interventions_idInterventions) ON Subjects.idSubjects=Intervention.Subjects_idSubjects INNER JOIN Weights ON Subjects.idSubjects=Weights.Subjects_idSubjects INNER JOIN SubjectType ON Subjects.idSubjects=SubjectType.Subjects_idSubjects;

-- Animal Subject Full View --
DROP VIEW IF EXISTS `mmeds_data1`.`AnimalSubjectTable`;
CREATE VIEW `mmeds_data1`.`AnimalSubjectTable` AS
SELECT DISTINCT idAnimalSubjects, idSubjectType AS idSubjectTypeAnimal, BirthDate, AnimalWeight, Sex AS SexAnimal, AnimalSubjectID, SubjectType, FacilityName, FacilityLocation, VendorName, VendorLocation, VendorStrainInfo, StrainName, StrainProducer, StrainID, SpeciesName, BreedingProgram, LightDarkCycle, Temperature, EnvironmentalEnrichment, TypeOfFacility, TypeOfBedding, TypeOfHousing, NumberOfCageCompanions, TankShape, TankMaterial, TankID, HousingStartDate, HousingEndDate, ChowStartDate, ChowEndDate, Company, ProductName, ProductCode FROM AnimalSubjects INNER JOIN SubjectType ON AnimalSubjects.idAnimalSubjects=SubjectType.AnimalSubjects_idAnimalSubjects INNER JOIN Facility ON AnimalSubjects.Facility_idFacility=Facility.idFacility INNER JOIN Vendor ON AnimalSubjects.Vendor_idVendor=Vendor.idVendor INNER JOIN (Strain INNER JOIN Species ON Strain.Species_idSpecies=Species.idSpecies) ON AnimalSubjects.Strain_idStrain=Strain.idStrain INNER JOIN Husbandry ON AnimalSubjects.Husbandry_idHusbandry=Husbandry.idHusbandry INNER JOIN (HousingDates INNER JOIN Housing ON HousingDates.Housing_idHousing=Housing.idHousing) ON AnimalSubjects.idAnimalSubjects=HousingDates.AnimalSubjects_idAnimalSubjects INNER JOIN (ChowDates INNER JOIN Chow ON ChowDates.Chow_idChow=Chow.idChow) ON AnimalSubjects.ChowDates_idChowDates=ChowDates.idChowDates;

-- Specimen Full View --
DROP VIEW IF EXISTS `mmeds_data1`.`SpecimenTable`;
CREATE VIEW `mmeds_data1`.`SpecimenTable` AS
SELECT DISTINCT idSpecimen, idSubjectType, AliquotID, AliquotWeight, AliquotWeightUnit, SpecimenBodySite, UberonCodeBodySite, Biome, CollectionSiteName, CollectionSiteTechnician, Depth, Elevation, Environment, Feature, Latitude, Longitude, Material, ExperimentName, ContactEmail, ContactName, PrimaryInvestigator, BarcodeSequence, LinkerPrimerSequence, RawDataID, RawDataNotes, RawDataDatePerformed, RawDataProcessor, RawDataProtocolID, FinishingStrategyCoverage, FinishingStrategyStatus, NumberOfContigs, SequencingMethod, TargetGene, ResultID, ResultsLocation, ResultsDatePerformed, ResultsProcessor, ResultsProtocolID, ResultsMethod, ResultsTool, ResultsToolVersion, SampleID, SampleWeight, SampleWeightUnit, SampleDatePerformed, SampleProcessor, SampleProtocolID, SampleProtocolNotes, SampleConditions, SampleTool, SampleToolVersion, SpecimenCollectionDate, SpecimenCollectionMethod, SpecimenCollectionTime, SpecimenID, SpecimenNotes, SpecimenWeight, SpecimenWeightUnit, StorageInstitution, StorageFreezer, RelevantLinks, StudyName, StudyType, SpecimenType, UberonCodeType FROM Specimen INNER JOIN Aliquot ON Specimen.idSpecimen=Aliquot.Specimen_idSpecimen INNER JOIN BodySite ON Specimen.BodySite_idBodySite=BodySite.idBodySite INNER JOIN CollectionSite ON Specimen.CollectionSite_idCollectionSite=CollectionSite.idCollectionSite INNER JOIN (Experiment INNER JOIN (Study INNER JOIN Lab ON Study.Lab_idLab=Lab.idLab) ON Experiment.Study_idStudy=Study.idStudy) ON Specimen.Experiment_idExperiment=Experiment.idExperiment INNER JOIN (StorageLocation INNER JOIN (Sample INNER JOIN (RawData INNER JOIN (RawDataProtocol INNER JOIN RawDataProtocols ON RawDataProtocol.RawDataProtocols_idRawDataProtocols=RawDataProtocols.idRawDataProtocols) ON RawData.RawDataProtocol_idRawDataProtocol=RawDataProtocol.idRawDataProtocol INNER JOIN (Results INNER JOIN (ResultsProtocol INNER JOIN ResultsProtocols ON ResultsProtocol.ResultsProtocols_idResultsProtocols=ResultsProtocols.idResultsProtocols) ON Results.ResultsProtocol_idResultsProtocol=ResultsProtocol.idResultsProtocol) ON RawData.Sample_idSample=Results.RawData_Sample_idSample) ON Sample.idSample=RawData.Sample_idSample INNER JOIN (SampleProtocol INNER JOIN SampleProtocols ON SampleProtocol.SampleProtocols_idSampleProtocols=SampleProtocols.idSampleProtocols) ON Sample.SampleProtocol_idSampleProtocol=SampleProtocol.idSampleProtocol) ON StorageLocation.idStorageLocation=Sample.StorageLocation_idStorageLocation) ON Specimen.StorageLocation_idStorageLocation=StorageLocation.idStorageLocation INNER JOIN Type ON Specimen.Type_idType=Type.idType INNER JOIN SubjectType ON Specimen.SubjectType_idSubjectType=SubjectType.idSubjectType;

-- Meta Analysis View --
DROP VIEW IF EXISTS `mmeds_data1`.`MetaAnalysisView`;
CREATE VIEW `mmeds_data1`.`MetaAnalysisView` AS
SELECT DISTINCT * FROM SpecimenTable INNER JOIN SubjectTable ON SpecimenTable.idSubjectType=SubjectTable.idSubjectTypeHuman INNER JOIN AnimalSubjectTable ON SpecimenTable.idSubjectType=AnimalSubjectTable.idSubjectTypeAnimal;

