"""
this:

- gets capital from the database (earmarked with a strategy name)
- runs a backtest using that capital level, and mongodb data
- gets the final positions and position buffers
- writes these into a table (earmarked with a strategy name)


"""

from syscore.objects import arg_not_supplied, missing_data

from sysdata.config.configdata import Config
from sysdata.data_blob import dataBlob

from sysobjects.production.optimal_positions import bufferedOptimalPositions
from sysobjects.production.tradeable_object import instrumentStrategy

from sysproduction.data.currency_data import dataCurrency
from sysproduction.data.capital import dataCapital
from sysproduction.data.contracts import dataContracts
from sysproduction.data.positions import dataOptimalPositions
from sysproduction.data.sim_data import get_sim_data_object_for_production

from sysproduction.data.backtest import store_backtest_state

from syslogdiag.log_to_screen import logtoscreen

from systems.provided.futures_chapter15.basesystem import futures_system
from systems.basesystem import System


class runSystemClassic(object):
    def __init__(
        self,
        data: dataBlob,
        strategy_name: str,
        backtest_config_filename=arg_not_supplied,
    ):

        if backtest_config_filename is arg_not_supplied:
            raise Exception("Need to supply config filename")

        self.data = data
        self.strategy_name = strategy_name
        self.backtest_config_filename = backtest_config_filename

    def run_backtest(self):
        strategy_name = self.strategy_name
        data = self.data

        base_currency, notional_trading_capital = self._get_currency_and_capital()

        system = self.system_method(
            notional_trading_capital=notional_trading_capital,
            base_currency=base_currency,
        )

        updated_buffered_positions(data, strategy_name, system)

        store_backtest_state(data, system, strategy_name=strategy_name)

    def _get_currency_and_capital(self):
        data = self.data
        strategy_name = self.strategy_name

        capital_data = dataCapital(data)
        notional_trading_capital = capital_data.get_capital_for_strategy(strategy_name)
        if notional_trading_capital is missing_data:
            # critical log will send email
            error_msg = (
                "Capital data is missing for %s: can't run backtest" % strategy_name
            )
            data.log.critical(error_msg)
            raise Exception(error_msg)

        currency_data = dataCurrency(data)
        base_currency = currency_data.get_base_currency()

        self.data.log.msg("Using capital of %s %.2f" % (base_currency, notional_trading_capital))

        return base_currency, notional_trading_capital

    # DO NOT CHANGE THE NAME OF THIS FUNCTION; IT IS HARDCODED INTO CONFIGURATION FILES
    # BECAUSE IT IS ALSO USED TO LOAD BACKTESTS
    def system_method(
        self, notional_trading_capital: float = arg_not_supplied, base_currency: str = arg_not_supplied
    ) -> System:
        data = self.data
        backtest_config_filename = self.backtest_config_filename

        system = production_classic_futures_system(
            data,
            backtest_config_filename,
            log=data.log,
            notional_trading_capital=notional_trading_capital,
            base_currency=base_currency,
        )

        return system


def production_classic_futures_system(
    data: dataBlob,
    config_filename: str,
    log=logtoscreen("futures_system"),
    notional_trading_capital: float = arg_not_supplied,
    base_currency: str = arg_not_supplied,
) -> System:

    log_level = "on"

    sim_data = get_sim_data_object_for_production(data)
    config = Config(config_filename)

    # Overwrite capital and base currency
    if notional_trading_capital is not arg_not_supplied:
        config.notional_trading_capital = notional_trading_capital

    if base_currency is not arg_not_supplied:
        config.base_currency = base_currency

    system = futures_system(data=sim_data, config=config)
    system._log = log

    system.set_logging_level(log_level)

    return system


def updated_buffered_positions(data: dataBlob, strategy_name: str, system: System):
    log = data.log

    data_optimal_positions = dataOptimalPositions(data)

    list_of_instruments = system.get_instrument_list()
    for instrument_code in list_of_instruments:
        lower_buffer, upper_buffer = get_position_buffers_from_system(
            system, instrument_code
        )
        position_entry = construct_position_entry(
            data=data,
            system=system,
            instrument_code=instrument_code,
            lower_buffer=lower_buffer,
            upper_buffer=upper_buffer,
        )
        instrument_strategy = instrumentStrategy(
            instrument_code=instrument_code, strategy_name=strategy_name
        )
        data_optimal_positions.update_optimal_position_for_instrument_strategy(
            instrument_strategy=instrument_strategy, position_entry=position_entry
        )
        log.msg(
            "New buffered positions %.3f %.3f"
            % (position_entry.lower_position, position_entry.upper_position),
            instrument_code=instrument_code,
        )


def get_position_buffers_from_system(system: System, instrument_code: str):
    buffers = system.portfolio.get_buffers_for_position(
        instrument_code
    )  # get the upper and lower edges of the buffer
    lower_buffer = buffers.iloc[-1].bot_pos
    upper_buffer = buffers.iloc[-1].top_pos

    return lower_buffer, upper_buffer


def construct_position_entry(
    data: dataBlob,
    system: System,
    instrument_code: str,
    lower_buffer: float,
    upper_buffer: float,
) -> bufferedOptimalPositions:

    diag_contracts = dataContracts(data)
    reference_price = system.rawdata.get_daily_prices(instrument_code).iloc[-1]
    reference_contract = diag_contracts.get_priced_contract_id(instrument_code)
    position_entry = bufferedOptimalPositions(
        lower_buffer, upper_buffer, reference_price, reference_contract
    )

    return position_entry
