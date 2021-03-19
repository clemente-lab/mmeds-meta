
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
`SpecimenInformation`,
`SpecimenCollectionTime`,
`SpecimenWeight`,
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
`SampleProtocolInformation`,
`SampleProtocolID`,
`SampleConditions`,
`SampleTool`,
`SampleToolVersion`
FROM ( `Sample` INNER JOIN
    ( `SampleProtocol` INNER JOIN
        `SampleProtocols` ON `SampleProtocols_idSampleProtocols` = `idSampleProtocols` )
    ON `SampleProtocol_idSampleProtocol` = `idSampleProtocol` );
