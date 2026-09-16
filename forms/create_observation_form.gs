/**
 * Creates the "Gowanus Canal Observation Survey" Google Form and its linked
 * response spreadsheet, based on the draft in the shared drive's
 * "Observational Survey" folder.
 *
 * HOW TO RUN (one time):
 *   1. Go to https://script.google.com and click "New project".
 *   2. Delete the placeholder code, paste this whole file, and click Save.
 *   3. Select the function `createGowanusForm` in the toolbar and click Run.
 *      Approve the permissions prompt (it runs as you, in your Drive).
 *   4. The execution log prints the form's edit URL, the public URL, and the
 *      response spreadsheet URL. Both files are moved into the shared
 *      "Observational Survey" folder if you have permission.
 *
 * Re-running creates a NEW form; it never edits an existing one. After small
 * wording tweaks made directly in the Forms editor, please mirror them here
 * so this file stays the reference copy.
 *
 * NOTE: Apps Script cannot create "file upload" questions, and enabling
 * photo uploads would force respondents to sign in to a Google account
 * anyway. Photos are therefore left out; if you want them, add a file-upload
 * question by hand in the Forms editor afterward.
 */

// The shared drive's "Observational Survey" folder.
const SHARED_FOLDER_ID = '1Dw8YrnaxgKkxKIaqtsQD_a-_TMN8uf2K';

function createGowanusForm() {
  const form = FormApp.create('Gowanus Canal Observation Survey');
  form.setDescription(
    'Record what you can see, smell, and hear at the Gowanus Canal. ' +
    'Observations cover the portion of the canal in front of you, across ' +
    'its width, up to about 50 feet north and south of where you stand.'
  );
  form.setCollectEmail(false);
  form.setLimitOneResponsePerUser(false);

  // ---------------- I am… ----------------
  form.addSectionHeaderItem().setTitle('I am…');

  form.addTextItem()
    .setTitle('Observer ID')
    .setHelpText(
      'Pick a 4-digit ID number for yourself and use it every time you ' +
      'make observations. It should be something you will remember — ' +
      'digits from your phone number, a date, or part of an address all work!'
    )
    .setRequired(true)
    .setValidation(
      FormApp.createTextValidation()
        .setHelpText('Please enter exactly 4 digits.')
        .requireTextMatchesPattern('^[0-9]{4}$')
        .build()
    );

  form.addListItem()
    .setTitle('Where are you?')
    .setRequired(true)
    .setChoiceValues([
      'Douglass Street',
      'Carroll Street Bridge',
      'Union Street Bridge',
      'Boathouse at 2nd Street',
      '3rd Street Bridge',
      '9th Street Bridge',
      'Bunker at 19th Street',
      'Somewhere else (enter coordinates below)',
    ]);

  form.addTextItem()
    .setTitle('If somewhere else: latitude')
    .setHelpText('You can find coordinates in Google Maps (e.g. 40.6768).')
    .setValidation(
      FormApp.createTextValidation()
        .setHelpText('Latitude near Gowanus is between 40 and 41.')
        .requireNumberBetween(40, 41)
        .build()
    );

  form.addTextItem()
    .setTitle('If somewhere else: longitude')
    .setHelpText('Longitude near Gowanus is negative (e.g. -73.9905).')
    .setValidation(
      FormApp.createTextValidation()
        .setHelpText('Longitude near Gowanus is between -75 and -73.')
        .requireNumberBetween(-75, -73)
        .build()
    );

  form.addDateItem()
    .setTitle("Today's date")
    .setRequired(true);

  form.addTimeItem()
    .setTitle('Time of observation')
    .setRequired(true);

  // ---------------- I can see… ----------------
  form.addSectionHeaderItem()
    .setTitle('I can see…')
    .setHelpText(
      'In the portion of the canal in front of you, across its width, to a ' +
      'max of about 50 feet to the north and south of where you are standing.'
    );

  form.addCheckboxItem()
    .setTitle('Do you see any litter in the water of the canal?')
    .setHelpText('Check all that apply.')
    .setChoiceValues([
      'Plastics',
      'Smoking-related items',
      'Balloons',
      'Medical supplies / personal hygiene',
      'Metals',
      'Large items',
      'Fishing gear',
      'Glass',
      'Miscellaneous',
      'No litter visible',
    ]);

  // TODO: the draft doc left the organism lists blank — these options are
  // placeholders chosen for the Gowanus; edit to taste before launch.
  form.addCheckboxItem()
    .setTitle('Do you see any dead organisms?')
    .setHelpText('Check all that apply.')
    .setChoiceValues([
      'Fish',
      'Crabs',
      'Jellyfish',
      'Birds',
      'Rats or other mammals',
      'Other (describe in notes at the end)',
      'No dead organisms visible',
    ]);

  form.addCheckboxItem()
    .setTitle('Do you see any living organisms?')
    .setHelpText('Check all that apply.')
    .setChoiceValues([
      'Fish',
      'Crabs',
      'Jellyfish',
      'Ducks or geese',
      'Cormorants',
      'Wading birds (egrets, herons)',
      'Other birds',
      'Turtles',
      'Rats or other mammals',
      'Insects',
      'Other (describe in notes at the end)',
      'No living organisms visible',
    ]);

  form.addCheckboxItem()
    .setTitle('Which words best describe what the water in the canal looks like?')
    .setHelpText('Check all that apply.')
    .setChoiceValues(['Brown', 'Green', 'Blue', 'Clear', 'Cloudy']);

  form.addMultipleChoiceItem()
    .setTitle('Do you see any oil sheen on the water?')
    .setRequired(true)
    .setChoiceValues([
      'Yes, at least 50% of the surface of the water is covered in oil sheen',
      'Yes, I see many spots or a large area covered in oil',
      'Yes, I see more than one spot of oil sheen',
      'Yes, I see one spot of oil sheen',
      'No, none at all',
    ]);

  // ---------------- I can smell… ----------------
  form.addSectionHeaderItem().setTitle('I can smell…');

  form.addCheckboxItem()
    .setTitle('What can you smell?')
    .setHelpText('Check all that apply.')
    .setChoiceValues([
      'Garbage',
      'Gasoline',
      'Something like rotten eggs',
      'Paint',
      'Poop',
      'Seawater',
      'Nothing notable',
    ]);

  // ---------------- I can hear… ----------------
  form.addSectionHeaderItem().setTitle('I can hear…');

  form.addCheckboxItem()
    .setTitle('What can you hear?')
    .setHelpText('Check all that apply.')
    .setChoiceValues([
      'Machinery',
      'Boats',
      'Traffic',
      'Airplanes',
      'People',
      'Subway trains',
      'Birds',
      'Running water',
      'Nothing notable',
    ]);

  // ---------------- Anything else ----------------
  form.addParagraphTextItem()
    .setTitle('Is there anything else you want to record?');

  // ---------------- Response spreadsheet ----------------
  const spreadsheet = SpreadsheetApp.create(
    'Gowanus Observation Survey (Responses)'
  );
  form.setDestination(FormApp.DestinationType.SPREADSHEET, spreadsheet.getId());

  // Move both files from My Drive into the shared folder, if permitted.
  try {
    const folder = DriveApp.getFolderById(SHARED_FOLDER_ID);
    DriveApp.getFileById(form.getId()).moveTo(folder);
    DriveApp.getFileById(spreadsheet.getId()).moveTo(folder);
    Logger.log('Moved form and spreadsheet into the shared folder.');
  } catch (e) {
    Logger.log(
      'Could not move files into the shared folder (' + e + '). ' +
      'They are in your My Drive; move them by hand.'
    );
  }

  Logger.log('Form editor:   ' + form.getEditUrl());
  Logger.log('Share this URL with observers: ' + form.getPublishedUrl());
  Logger.log('Responses spreadsheet: ' + spreadsheet.getUrl());
}
