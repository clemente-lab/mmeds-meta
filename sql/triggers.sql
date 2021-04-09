DELIMITER //

DROP TRIGGER IF EXISTS specimen_weight_update //

CREATE TRIGGER specimen_weight_update
AFTER INSERT ON Aliquot
FOR EACH ROW
BEGIN
-- Get the current weight of the associated Specimen
-- NEW is a temporary table containing the data from the INSERT call
SELECT SpecimenWeight INTO @CurrentSpecimenWeight FROM Specimen WHERE idSpecimen = NEW.Specimen_idSpecimen;
-- Subject the weight of the new Aliquot from the Specimen
UPDATE Specimen SET SpecimenWeight = @CurrentSpecimenWeight - NEW.AliquotWeight WHERE idSpecimen = NEW.Specimen_idSpecimen;
END //


DROP TRIGGER IF EXISTS aliquot_weight_update //

CREATE TRIGGER aliquot_weight_update
AFTER INSERT ON Sample
FOR EACH ROW
BEGIN
-- Get the current weight of the associated Specimen
-- NEW is a temporary table containing the data from the INSERT call
SELECT AliquotWeight INTO @CurrentAliquotWeight FROM Aliquot WHERE `idAliquot` = `NEW`.`Aliquot_idAliquot`;
-- Subject the weight of the new Sample from the Aliquot
UPDATE Aliquot SET AliquotWeight = @CurrentAliquotWeight - NEW.`SampleWeight` WHERE `idAliquot` = `NEW`.`Aliquot_idAliquot`;
END //

DELIMITER ;
