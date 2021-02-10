import argparse
import csv
import re
import warnings

import numpy as np
import pandas as pd
import plotly.graph_objects as go


class GraphGroups:
    def __init__(self, df):
        self.df = df
        self.left_graphs = set()
        self.right_graphs = set()
        self.groups = dict()

    def add_group(self, label, ltitle, lgraphs, rtitle='', rgraphs=''):
        def filter_columns(graphs):
            return self.df.filter(regex=graphs).columns.to_list() if graphs else []
        def infer_axis_type(graphs):
            is_numeric = np.dtype('O') not in self.df[graphs].dtypes.to_list()
            return 'linear' if is_numeric else 'category'
        lgraphs = filter_columns(lgraphs)
        rgraphs = filter_columns(rgraphs)
        self.groups[label] = dict(label=label,
                                  ltitle=ltitle,
                                  lgraphs=lgraphs,
                                  ltype=infer_axis_type(lgraphs),
                                  rtitle=rtitle,
                                  rgraphs=rgraphs,
                                  rtype=infer_axis_type(rgraphs),
                                  )
        self.left_graphs.update(lgraphs)
        if rgraphs is not None:
            self.right_graphs.update(rgraphs)

    def create_default_groups(self):
        groups = (
            2 * ('Core perf',) + ('perf',),
            2 * ('Core Effective Clock',) +('Core [\w\s]+ Effective Clock',),
            2 * ('Core Usage',) + ('Core [\w\s]+ Usage',),
            2 * ('Temperature',) + ('\[°[C|F]\]',),    # HWiNFO allows either Celcius or Fahrenheit
            2 * ('Throttling',) + ('Throttling',),
            2 * ('Voltage',) + ('\[V\]',),
            2 * ('Current',) + ('\[A\]',),
            2 * ('Power',) + ('\[W\]',),
            2 * ('Fans',) + ('\[RPM\]',),
            ('CPU Fan/Power', 'RPM', 'CPU \[RPM\]', 'Power', 'CPU Package Power \(SMU\) \[W\]'),
        )
        for args in groups:
            self.add_group(*args)
    
    def create_figure(self):
        left = [col for col in self.df.columns if col in self.left_graphs]
        right = [col for col in self.df.columns if col in self.right_graphs]
        fig = go.Figure()
        for label in left:
            fig.add_trace(go.Scatter(
                x=self.df['Time'], y=self.df[label], name=label, visible=False))
        for label in right:
            fig.add_trace(go.Scatter(
                x=self.df['Time'], y=self.df[label], name=label, visible=False, yaxis='y2'))
        buttons = []
        for group, values in self.groups.items():
            buttons.append(
                dict(method='update',
                     label=group,
                     args=[{'visible':
                            ([graph in values['lgraphs'] for graph in left] +
                             [graph in values['rgraphs'] for graph in right])},
                           {'yaxis.title': values['ltitle'],
                            'yaxis.type': values['ltype'],
                            'yaxis2.title': values['rtitle'],
                            'yaxis2.type': values['rtype'],
                            'yaxis2.visible': bool(values['rgraphs'])},
                           ],
                     ))
        updatemenus = [dict(buttons=buttons, direction='down', showactive=True)]
        fig.update_layout(
            updatemenus=updatemenus,
            title='HWiNFO measurements ({})'.format(self.df['Date'][0]),
            title_x=0.5,
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(title='Time', nticks=20),
            yaxis2=dict(overlaying='y', side='right', visible=False),
        )
        return fig


def load_csv(file, sep=',', encoding='latin-1'):
    try:
        df = pd.read_csv(file, sep=sep, encoding=encoding)
        del df[df.columns[-1]]
        df.drop(df.tail(2).index, inplace=True)
    except pd.errors.ParserError as e:
        warnings.warn(
            'A new sensor probably came online halfway through the logging '
            'session, which added a new column and broke the CSV standard. '
            'A custom method will be used to read the data. Original error '
            'message:\n{}'.format(e.args[0]))
        with open(file) as f:
            reader = csv.reader(f)
            rows = [row for row in reader]
        # The header written at the end of the file contains all sensors.
        # Make that the proper header and get rid of any other junk rows.
        rows[0] = rows[-2]
        del rows[-2:]
        # Pad all rows missing columns to complete the table
        length = len(rows[0]) - 1
        for i, row in enumerate(rows):
            # Must remove the empty row at the end before padding
            row = row[:-1]
            rows[i] = row + [None] * (length - len(row))
        df = pd.DataFrame(data=rows[1:], columns=rows[0])
    # Coerce data from str to appropriate type (int/float/str)
    for column in df.columns:
        try:
            df[column] = pd.to_numeric(df[column])
        except ValueError:
            pass
    return df


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
    description='Plot data from HWiNFO logs.',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        'path',
        help='The logfile created using HWiNFO'
    )
    parser.add_argument(
        '--groups', '-g',
        type=str,
        nargs='+',
        help='Add additional graph groups with the syntax "label,ltitle,lgraphs,rtitle,rgraphs." '
        '"label" is the menu name of the group and it must be unique to every other one. '
        '"lgraphs" and "rgraphs" are the labels of the left and right y-axes respectively. '
        '"ltitle" and "rtitle" are the regex patterns for what columns from the file to include '
        'for the left and right y-axes respectively. "label", "ltitle", and "lgraphs" are mandatory.'
    )
    parser.add_argument(
        '--encoding', '-e',
        type=str,
        default='latin-1',
        help='Encoding choice of the log file. Use this if you have problems '
        'parsing the file. Alternatively, you can save the file with a different '
        'encoding, such as utf-8, and use that. See https://docs.python.org/'
        '3/library/codecs.html#standard-encodings for more options.'
    )
    parser.add_argument(
        '--separator', '-s',
        type=str, default=',',
        help='Separator character of the csv file. Use this if you have changed '
        'the separator from the HWiNFO options.'
    )
    args = parser.parse_args()

    df = load_csv(args.path, args.separator, args.encoding)
    g = GraphGroups(df)
    g.create_default_groups()
    if args.groups:
        for group in args.groups:
            g.add_group(*group.split(','))
    fig = g.create_figure()
    fig.show()
